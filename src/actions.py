def gerar_notificacao(search_name, tipo, valor, tentativas):
    if search_name == "T1110 - Brute Force (sudo authentication)":
        assunto = f"[SOAR] Brute force detected: {valor}"
        corpo = (
            f"Alert: {search_name}\n"
            f"User: {valor}\n"
            f"Attempts: {tentativas}\n\n"
            f"pam_faillock already blocked locally, this notification is only "
            f"for visibility — there's no blocking action to take"
        )
        return assunto, corpo

    raise ValueError(f"Alert type without notification rule: {search_name}")