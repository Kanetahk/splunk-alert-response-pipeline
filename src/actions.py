def gerar_notificacao(search_name, tipo, valor, tentativas, severity):
    if search_name == "T1110 - Brute Force (sudo authentication)":
        urgente = severity == "high"
        assunto = f"[SOAR]{' [URGENT]' if urgente else ''} Brute force detected: {valor}"
        corpo = (
            f"Alert: {search_name}\n"
            f"Severity: {severity}\n"
            f"User: {valor}\n"
            f"Attempts: {tentativas}\n\n"
            f"pam_faillock has already enforced the local lockout; this notification is for visibility only."
        )
        return assunto, corpo, urgente

    raise ValueError(f"Alert type with no notification rule: {search_name}")