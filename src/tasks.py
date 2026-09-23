import os
from celery import Celery
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from model import Base, Alerta
from indicators import extrair_indicador
from actions import gerar_notificacao
from notifications import enviar_email

load_dotenv()

app = Celery('tasks', broker='redis://127.0.0.1:6379/0')

caminho_atual = os.path.dirname(os.path.abspath(__file__))  # src/
caminho_banco = os.path.join(caminho_atual, '..', 'data', 'soar.db')
engine = create_engine(f"sqlite:///{caminho_banco}")
Base.metadata.create_all(engine)

@app.task
def processar_alerta(search_name, result):
    tipo, valor, tentativas = extrair_indicador(search_name, result)

    with Session(engine) as session:
        novo = Alerta(
            search_name=search_name,
            indicator_type=tipo,
            indicator_value=valor,
            attempts=tentativas,
        )
        session.add(novo)
        session.commit()
        print(f"Saved Alert: {tipo}={valor}, attempts={tentativas}, id={novo.id}")

    assunto, corpo = gerar_notificacao(search_name, tipo, valor, tentativas)
    enviar_email(assunto, corpo)
    print(f"Notification sent: {assunto}")

    return f"{tipo}={valor} processed and notified"