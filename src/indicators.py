def extrair_indicador(search_name: str, result: dict) -> tuple[str, str, int, str]:
    """Retorna (tipo_de_indicador, valor, tentativas) a partir do result bruto do Splunk."""
    if search_name == "T1110 - Brute Force (sudo authentication)":
        return "user", result["user"], int(result["attempts"]), result.get("severity", "medium")
    # próximo tipo de alerta entra aqui, com seu próprio elif
    raise ValueError(f"Alert type with no extraction rule: {search_name}")