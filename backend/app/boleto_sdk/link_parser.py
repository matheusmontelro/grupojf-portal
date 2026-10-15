# Boleto SDK link parser.
class LinkParser:
   
    @staticmethod
    def _extract_boleto_url(response):
        """
        Extrai a URL pública do boleto PDF do cabeçalho 'Link'.

        Args:
            response (requests.Response): Resposta HTTP.

        Returns:
            str: URL do PDF do boleto, se presente.
        """
        link_header = response.headers.get("Link", "")
        
        # Verifica se o cabeçalho está vazio
        if not link_header:
            return None

        # Processa os links do cabeçalho
        links = link_header.split(", ")
        for link in links:
            # Verifica se o 'rel="public-boleto-pdf"' está presente
            if 'rel="public-boleto-pdf"' in link:
                # Extrai a URL entre os caracteres < e >
                start = link.find("<") + 1
                end = link.find(">")
                if start != 0 and end != -1:
                    return link[start:end]

        # Retorna None se o 'rel' não foi encontrado
        return None
