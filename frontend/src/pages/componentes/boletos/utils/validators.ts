// src/pages/componentes/boletos/utils/validators.ts

/**
 * Valida se um CPF é válido (incluindo verificação de dígitos).
 * Implementa o algoritmo de validação de CPF oficial.
 */
export function validateCPF(cpf: string): boolean {
    const cleanCPF = cpf.replace(/\D/g, '');
    
    // Verifica o tamanho
    if (cleanCPF.length !== 11) return false;
    
    // Verifica dígitos iguais (caso comum de CPF inválido como 11111111111)
    if (/^(\d)\1{10}$/.test(cleanCPF)) return false;
    
    // Algoritmo de validação do CPF
    let sum = 0;
    let remainder;
    
    // Primeiro dígito verificador
    for (let i = 1; i <= 9; i++) {
      sum += parseInt(cleanCPF.substring(i - 1, i)) * (11 - i);
    }
    
    remainder = (sum * 10) % 11;
    if (remainder === 10 || remainder === 11) remainder = 0;
    if (remainder !== parseInt(cleanCPF.substring(9, 10))) return false;
    
    // Segundo dígito verificador
    sum = 0;
    for (let i = 1; i <= 10; i++) {
      sum += parseInt(cleanCPF.substring(i - 1, i)) * (12 - i);
    }
    
    remainder = (sum * 10) % 11;
    if (remainder === 10 || remainder === 11) remainder = 0;
    if (remainder !== parseInt(cleanCPF.substring(10, 11))) return false;
    
    return true;
  }
  
  /**
   * Valida um endereço de email usando regex.
   */
  export function validateEmail(email: string): boolean {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
  }
  
  /**
   * Valida um número de telefone brasileiro.
   * Aceita formatos como: (00)00000-0000, 00000000000, etc.
   */
  export function validatePhone(phone: string): boolean {
    const digits = phone.replace(/\D/g, '');
    // Remove o código do país (55) se presente
    const phoneDigits = digits.startsWith('55') ? digits.substring(2) : digits;
    
    // Telefone deve ter 10 ou 11 dígitos (com o 9 na frente para celulares)
    return phoneDigits.length >= 10 && phoneDigits.length <= 11;
  }
  
  /**
   * Valida um CEP brasileiro (formato 00000-000 ou 00000000).
   */
  export function validateCEP(cep: string): boolean {
    const digits = cep.replace(/\D/g, '');
    return digits.length === 8;
  }
  
  /**
   * Verifica se uma data é válida e não está no futuro.
   * Para datas de nascimento.
   */
  export function validateBirthdate(date: string): boolean {
    if (!date) return false;
    
    const birthDate = new Date(date);
    const today = new Date();
    
    // Verifica se é uma data válida
    if (isNaN(birthDate.getTime())) return false;
    
    // Verifica se não está no futuro
    if (birthDate > today) return false;
    
    // Verifica se não é muito antiga (mais de 120 anos)
    const maxAge = new Date();
    maxAge.setFullYear(maxAge.getFullYear() - 120);
    if (birthDate < maxAge) return false;
    
    return true;
  }
  
  /**
   * Valida um valor monetário, verificando se é positivo e não zero.
   */
  export function validateMonetaryValue(value: string | number): boolean {
    let numValue: number;
    
    if (typeof value === 'string') {
      // Remove formatação R$ e converte ',' para '.'
      const cleanValue = value.replace(/[R$\s.]/g, '').replace(',', '.');
      numValue = parseFloat(cleanValue);
    } else {
      numValue = value;
    }
    
    return !isNaN(numValue) && numValue > 0;
  }
  
  /**
   * Valida o número de parcelas, garantindo que está entre min e max.
   */
  export function validateParcelas(parcelas: number, min = 1, max = 24): boolean {
    return parcelas >= min && parcelas <= max && Number.isInteger(parcelas);
  }
  
  /**
   * Valida o formulário completo e retorna os erros encontrados.
   */
  export function validateBoletoForm(formData: any): Record<string, string> {
    const errors: Record<string, string> = {};
    
    // Validação de dados do cliente
    if (!formData.nomeCliente?.trim()) {
      errors.nomeCliente = 'Nome do cliente é obrigatório';
    }
    
    const cpfDigits = formData.cpfCnpj?.replace(/\D/g, '');
    if (!cpfDigits || cpfDigits.length !== 11) {
      errors.cpfCnpj = 'CPF deve conter 11 dígitos';
    } else if (!validateCPF(cpfDigits)) {
      errors.cpfCnpj = 'CPF inválido';
    }
    
    if (!formData.email?.trim()) {
      errors.email = 'E-mail é obrigatório';
    } else if (!validateEmail(formData.email)) {
      errors.email = 'Formato de e-mail inválido';
    }
    
    if (!formData.birthdate) {
      errors.birthdate = 'Data de nascimento é obrigatória';
    } else if (!validateBirthdate(formData.birthdate)) {
      errors.birthdate = 'Data de nascimento inválida';
    }
    
    // Validação para dependente menor
    if (formData.isMinorDependent && !formData.dependentName?.trim()) {
      errors.dependentName = 'Nome do dependente é obrigatório';
    }
    
    // Validação do telefone (opcional)
    if (formData.phone && !validatePhone(formData.phone)) {
      errors.phone = 'Telefone inválido';
    }
    
    // Validação do endereço
    if (!formData.cep?.trim()) {
      errors.cep = 'CEP é obrigatório';
    } else if (!validateCEP(formData.cep)) {
      errors.cep = 'CEP inválido';
    }
    
    if (!formData.street?.trim()) {
      errors.street = 'Rua é obrigatória';
    }
    
    if (!formData.streetNumber?.trim()) {
      errors.streetNumber = 'Número é obrigatório';
    }
    
    if (!formData.neighborhood?.trim()) {
      errors.neighborhood = 'Bairro é obrigatório';
    }
    
    if (!formData.city?.trim()) {
      errors.city = 'Cidade é obrigatória';
    }
    
    if (!formData.uf?.trim()) {
      errors.uf = 'UF é obrigatória';
    }
    
    // Validação de pagamento
    if (!validateMonetaryValue(formData.valorBRL)) {
      errors.valorBRL = 'Valor deve ser maior que zero';
    }
    
    if (!validateParcelas(formData.numParcelas)) {
      errors.numParcelas = 'Número de parcelas inválido';
    }
    
    if (formData.daysUntilDue <= 0) {
      errors.daysUntilDue = 'Prazo para vencimento deve ser maior que zero';
    }
    
    if (!formData.unidade?.trim()) {
      errors.unidade = 'Unidade é obrigatória';
    }
    
    return errors;
  }