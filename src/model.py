from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Alerta(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_name: Mapped[str] = mapped_column()
    indicator_type: Mapped[str] = mapped_column()
    indicator_value: Mapped[str] = mapped_column()
    attempts: Mapped[int] = mapped_column()