from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    telefono = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    cuit = Column(String, nullable=True)
    rubro = Column(String, nullable=True)
    website = Column(String, nullable=True)

    empleados = relationship("Empleado", back_populates="empresa")

class Empleado(Base):
    __tablename__ = "empleados"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    empresa_id = Column(Integer, ForeignKey("empresas.id"))
    cargo = Column(String, nullable=True)
    email = Column(String, nullable=False, server_default='sin_correo@empresa.com')
    fecha_ingreso = Column(String, nullable=True)
    salario = Column(Integer, nullable=True)
    departamento = Column(String, nullable=True)

    empresa = relationship("Empresa", back_populates="empleados")

class Proyecto(Base):
    __tablename__ = "proyectos"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    descripcion = Column(String, nullable=True)
    presupuesto = Column(Integer, nullable=True)
    estado = Column(String, nullable=True)
