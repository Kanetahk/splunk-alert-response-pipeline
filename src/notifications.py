import smtplib
import ssl
import os
from email.mime.text import MIMEText

def enviar_email(assunto, corpo, urgente=False):
    remetente = os.getenv("EMAIL_SENDER")
    senha = os.getenv("EMAIL_APP_PASSWORD")
    destinatario = os.getenv("EMAIL_RECIPIENT")

    msg = MIMEText(corpo)
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    if urgente:
        msg["X-Priority"] = "1"
        msg["Importance"] = "High"

    contexto = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as servidor:
        servidor.starttls(context=contexto)
        servidor.login(remetente, senha)
        servidor.send_message(msg)