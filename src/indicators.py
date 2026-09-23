def extrair_indicador(search_name: str, result: dict) -> tuple[str, str, int]:
    """Retorna (tipo_de_indicador, valor, tentativas) a partir do result bruto do Splunk."""
    if search_name == "T1110 - Brute Force (sudo authentication)":
        return "user", result["user"], int(result["attempts"])

    # próximo tipo de alerta entra aqui, com seu próprio elif
    raise ValueError(f"Alert type without extraction rule: {search_name}")