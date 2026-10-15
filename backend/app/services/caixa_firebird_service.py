"""Consulta mensal de caixa em fontes Firebird configuradas localmente.

O arquivo de configuracao nunca e versionado: sem ele, a consulta falha fechada.
"""
from __future__ import annotations

import json
import multiprocessing
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from queue import Empty, Queue
from threading import BoundedSemaphore, Thread
from time import monotonic
from typing import Any


UNIDADES = {
    "Nova Iguaçu 1": ("ni1_clinico", "ni1_contratos"),
    "São João de Meriti": ("sjm_clinico", "sjm_contratos"),
    "Vilar dos Teles": ("vilar_clinico", "vilar_contratos"),
}
CATEGORIAS = ("manutencao", "adesao", "raio_panoramico", "odc", "rec_cred", "vendas", "nao_classificado")

# A classificacao e deliberadamente por alias e codigo, nunca por descricao livre.
CODIGOS = {
    "ni1_clinico": {"vendas": {"10", "22", "23", "43", "181", "194"}, "manutencao": {"50", "52", "55", "59", "123", "183", "196", "704"}, "rec_cred": {"47", "84", "86", "90", "182", "195", "983"}, "adesao": {"554", "560"}},
    "ni1_contratos": {"odc": {"18", "51", "53", "57", "85", "92"}},
    "sjm_clinico": {"vendas": {"10", "15", "20", "42", "194"}, "manutencao": {"49", "50", "52", "54", "115", "183"}, "rec_cred": {"46", "84", "86", "88", "983"}, "adesao": {"554", "561"}},
    "sjm_contratos": {"odc": {"14", "51", "53", "55", "91"}, "adesao": {"38"}},
    "vilar_clinico": {"vendas": {"10", "14", "16", "31", "191", "194"}, "manutencao": {"45", "50", "52", "54", "82", "173"}, "rec_cred": {"35", "84", "86", "88", "983"}, "adesao": {"554", "561", "562"}},
    "vilar_contratos": {"odc": {"14", "51", "53", "55", "81"}},
}
# GRUPO_FORMAS_PAGTO usa OUTROS para boleto e cartao online; portanto esses
# codigos recebem rótulos estáticos, sem inferência do texto no banco.
FORMAS_ESPECIAIS = {
    ("ni1_clinico", "181"): "Boleto DeltaPag", ("ni1_clinico", "182"): "Boleto DeltaPag",
    ("ni1_clinico", "183"): "Boleto DeltaPag", ("ni1_clinico", "194"): "Cartão online",
    ("ni1_clinico", "195"): "Cartão online", ("ni1_clinico", "196"): "Cartão online",
    ("ni1_contratos", "85"): "Boleto DeltaPag", ("ni1_contratos", "92"): "Cartão online",
    ("sjm_clinico", "183"): "Boleto DeltaPag", ("sjm_clinico", "194"): "Cartão online",
    ("sjm_contratos", "91"): "Boleto DeltaPag", ("vilar_clinico", "173"): "Boleto DeltaPag",
    ("vilar_clinico", "191"): "Cartão afins", ("vilar_clinico", "194"): "Cartão online",
    ("vilar_contratos", "81"): "Boleto DeltaPag",
}
_REQUESTS = BoundedSemaphore(4)


@dataclass
class CaixaFonteResultado:
    unidade: str
    alias: str
    dias: list[dict[str, Any]] = field(default_factory=list)
    formas_pagamento: dict[str, int] = field(default_factory=dict)


def _centavos(valor: Any) -> int:
    return int((Decimal(str(valor)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)) * 100)


def _categoria(alias: str, codigo: Any) -> str:
    codigo_normalizado = str(codigo).strip()
    for categoria, codigos in CODIGOS.get(alias, {}).items():
        if codigo_normalizado in codigos:
            return categoria
    return "nao_classificado"


def _mes_seguinte(mes: date) -> date:
    return date(mes.year + (mes.month == 12), 1 if mes.month == 12 else mes.month + 1, 1)


def _consulta_fonte_processo(config: dict[str, Any], inicio: date, fim: date, conexao_retorno: Any) -> None:
    """Executa fora do processo web, permitindo encerrar driver bloqueado no prazo."""
    conexao = None
    try:
        import fdb  # importacao tardia preserva a API indisponivel sem dependencia instalada
        biblioteca = config.get("library_path")
        if biblioteca:
            fdb.load_api(biblioteca)
        tpb = fdb.TPB()
        tpb.access_mode = fdb.isc_tpb_read
        tpb.isolation_level = (fdb.isc_tpb_read_committed, fdb.isc_tpb_rec_version)
        tpb.lock_resolution = fdb.isc_tpb_nowait
        conexao = fdb.connect(
            dsn=config["dsn"], user=config["user"], password=config["password"],
            charset=config.get("charset", "WIN1252"), no_db_triggers=True, no_gc=True, isolation_level=tpb.render(),
        )
        transacao = conexao.main_transaction
        transacao.default_action = "rollback"
        transacao.begin()
        if transacao.trans_info(fdb.isc_info_tra_access) != fdb.isc_info_tra_readonly:
            raise RuntimeError("transacao sem leitura")
        cursor = transacao.cursor()
        cursor.execute(
            "SELECT CAST(C.DATA AS DATE), C.TIPO, C.CALCULO, C.VALOR, G.NOME "
            "FROM CXD555 C LEFT JOIN CRD013 D ON C.TIPO = D.CODIGO "
            "LEFT JOIN GRUPO_FORMAS_PAGTO G ON G.CODIGO = D.GRUPO_FORMA_PAGTO "
            "WHERE C.DATA >= ? AND C.DATA < ? ORDER BY C.DATA, C.LANCTO", (inicio, fim))
        lancamentos = cursor.fetchmany(50000)
        if cursor.fetchone() is not None:
            raise RuntimeError("limite de lancamentos excedido")
        cursor.execute("SELECT CAST(DATA AS DATE), ABRIU, FECHOU FROM DATMOV WHERE DATA >= ? AND DATA < ?", (inicio, fim))
        fechamentos = cursor.fetchmany(5000)
        if cursor.fetchone() is not None:
            raise RuntimeError("limite de fechamentos excedido")
        transacao.rollback()
        conexao_retorno.send(("ok", lancamentos, fechamentos))
    except Exception:
        conexao_retorno.send(("erro",))
    finally:
        if conexao:
            try:
                conexao.rollback()
            except Exception:
                pass
            try:
                conexao.close()
            except Exception:
                pass
        conexao_retorno.close()


class CaixaFirebirdService:
    def __init__(self) -> None:
        try:
            self.timeout = max(1, min(int(os.getenv("CAIXA_FIREBIRD_TIMEOUT_SECONDS", "15")), 30))
        except ValueError:
            self.timeout = 15

    def _configuracao(self) -> dict[str, Any] | None:
        caminho = os.getenv("CAIXA_FIREBIRD_CONFIG_PATH")
        if not caminho:
            return None
        try:
            configuracao = json.loads(Path(caminho).read_text(encoding="utf-8"))
            return configuracao if isinstance(configuracao, dict) and isinstance(configuracao.get("sources"), dict) else None
        except (OSError, ValueError):
            return None

    def consultar_mes(self, mes: date, unidades: tuple[str, ...]) -> dict[str, Any]:
        configuracao = self._configuracao()
        if not configuracao:
            return {"fontes": [], "falhas": [{"codigo": "configuracao_indisponivel"}], "atualizado_em": None}
        fontes = []
        falhas = []
        inicio, fim = mes, _mes_seguinte(mes)
        tarefas = [(unidade, alias, configuracao.get("sources", {}).get(alias)) for unidade in unidades for alias in UNIDADES[unidade]]
        with ThreadPoolExecutor(max_workers=min(3, len(tarefas))) as executor:
            futuros = {executor.submit(self._consultar_fonte, unidade, alias, fonte, inicio, fim): (unidade, alias) for unidade, alias, fonte in tarefas}
            for futuro in as_completed(futuros):
                unidade, alias = futuros[futuro]
                try:
                    resultado = futuro.result()
                except Exception:
                    resultado = "fonte_indisponivel"
                if isinstance(resultado, CaixaFonteResultado):
                    fontes.append(resultado)
                else:
                    falhas.append({"unidade": unidade, "alias": alias, "codigo": resultado})
        return {"fontes": fontes, "falhas": falhas, "atualizado_em": datetime.utcnow().isoformat() + "Z"}

    def _consultar_fonte(self, unidade: str, alias: str, config: dict[str, Any] | None, inicio: date, fim: date) -> CaixaFonteResultado | str:
        if not isinstance(config, dict) or any(
            not isinstance(config.get(campo), str) or not config[campo].strip()
            for campo in ("dsn", "user", "password")
        ):
            return "fonte_indisponivel"
        if any(campo in config and not isinstance(config[campo], str) for campo in ("charset", "library_path")):
            return "fonte_indisponivel"
        if not _REQUESTS.acquire(blocking=False):
            return "capacidade_indisponivel"
        processo = recebimento = envio = None
        iniciado = False
        liberar_capacidade = True
        try:
            contexto = multiprocessing.get_context("spawn")
            recebimento, envio = contexto.Pipe(duplex=False)
            processo = contexto.Process(target=_consulta_fonte_processo, args=(config, inicio, fim, envio))
            processo.start()
            iniciado = True
            envio.close()
            prazo = monotonic() + self.timeout
            if not recebimento.poll(self.timeout):
                return "prazo_excedido"
            # poll pode sinalizar apenas o primeiro byte. A recepcao completa
            # tambem respeita o prazo, mesmo se o filho parar no meio do envio.
            retornos: Queue = Queue(maxsize=1)

            def receber() -> None:
                try:
                    retornos.put((True, recebimento.recv()))
                except Exception:
                    retornos.put((False, None))

            Thread(target=receber, daemon=True).start()
            try:
                recebido, retorno = retornos.get(timeout=max(0, prazo - monotonic()))
            except Empty:
                return "prazo_excedido"
            if not recebido or not isinstance(retorno, tuple) or len(retorno) != 3 or retorno[0] != "ok":
                return "fonte_indisponivel"
            return self.agrupar_lancamentos(unidade, alias, retorno[1], retorno[2])
        except Exception:
            return "fonte_indisponivel"
        finally:
            if processo is not None and iniciado:
                processo.join(0.1)
                if processo.is_alive():
                    processo.terminate()
                    processo.join(0.5)
                if processo.is_alive():
                    # Somente o filho criado acima, nunca um processo do servidor.
                    processo.kill()
                    processo.join(0.5)
                liberar_capacidade = not processo.is_alive()
            for canal in (recebimento, envio):
                if canal is not None:
                    canal.close()
            if processo is not None and not (iniciado and not liberar_capacidade):
                fechar = getattr(processo, "close", None)
                if fechar is not None:
                    fechar()
            if liberar_capacidade:
                _REQUESTS.release()

    def agrupar_lancamentos(self, unidade: str, alias: str, lancamentos: list[Any], fechamentos: list[Any]) -> CaixaFonteResultado:
        por_dia: dict[date, dict[str, Any]] = {}
        for linha in lancamentos:
            data_lancamento, tipo, calculo, valor, forma = linha
            dia = data_lancamento.date() if isinstance(data_lancamento, datetime) else data_lancamento
            item = por_dia.setdefault(dia, {"data": dia, "total_centavos": 0, "categorias": {categoria: 0 for categoria in CATEGORIAS}, "formas_pagamento": {}, "manutencoes_recebidas": 0, "codigos_nao_classificados": [], "codigos_nao_homologados": []})
            codigo = str(tipo).strip()
            if calculo != "+":
                if codigo != "36" and codigo not in item["codigos_nao_homologados"]:
                    item["codigos_nao_homologados"].append(codigo)
                continue
            valor_centavos = _centavos(valor)
            if valor_centavos <= 0:
                if codigo not in item["codigos_nao_homologados"]:
                    item["codigos_nao_homologados"].append(codigo)
                continue
            categoria = _categoria(alias, codigo)
            item["total_centavos"] += valor_centavos
            item["categorias"][categoria] += valor_centavos
            if categoria == "manutencao":
                item["manutencoes_recebidas"] += 1
            if categoria == "nao_classificado" and codigo not in item["codigos_nao_classificados"]:
                item["codigos_nao_classificados"].append(codigo)
            nome_forma = FORMAS_ESPECIAIS.get((alias, codigo), str(forma or "Não informado").strip() or "Não informado")
            item["formas_pagamento"][nome_forma] = item["formas_pagamento"].get(nome_forma, 0) + valor_centavos
        flags: dict[date, list[tuple[str, str]]] = {}
        for data_mov, abriu, fechou in fechamentos:
            dia = data_mov.date() if isinstance(data_mov, datetime) else data_mov
            flags.setdefault(dia, []).append((str(abriu).upper(), str(fechou).upper()))
            por_dia.setdefault(dia, {"data": dia, "total_centavos": 0, "categorias": {categoria: 0 for categoria in CATEGORIAS}, "formas_pagamento": {}, "manutencoes_recebidas": 0, "codigos_nao_classificados": [], "codigos_nao_homologados": []})
        for dia, item in por_dia.items():
            estados = flags.get(dia, [])
            if any(abriu == "S" and fechou != "S" for abriu, fechou in estados):
                item["status_fechamento"] = "aberto"
            elif estados and all(abriu == "S" and fechou == "S" for abriu, fechou in estados):
                item["status_fechamento"] = "fechado"
            elif item["total_centavos"]:
                item["status_fechamento"] = "sem_fechamento"
            else:
                item["status_fechamento"] = "sem_movimento"
        formas: dict[str, int] = {}
        for item in por_dia.values():
            for nome, valor in item["formas_pagamento"].items():
                formas[nome] = formas.get(nome, 0) + valor
        return CaixaFonteResultado(unidade=unidade, alias=alias, dias=sorted(por_dia.values(), key=lambda item: item["data"]), formas_pagamento=formas)
