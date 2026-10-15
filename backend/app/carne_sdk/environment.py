class Environment:
    """
    Gerencia os ambientes (produção e sandbox) para a SDK de Carnês.
    """
    SANDBOX = "https://api-sandbox.bempaggo.io/api/v2"  # Correto conforme docs
    PRODUCTION = "https://api.bempaggo.io/api/v2"  # Mantém o mesmo

    @staticmethod
    def get_base_url(environment):
        """
        Retorna a URL base para o ambiente especificado.

        Args:
            environment (str): O ambiente ("sandbox" ou "production").

        Returns:
            str: A URL base correspondente.
        """
        if environment == "production":
            return Environment.PRODUCTION
        elif environment == "sandbox":
            return Environment.SANDBOX
        else:
            raise ValueError("Ambiente inválido. Use 'sandbox' ou 'production'.")