# =============================================================================
# HISTORY CLINIC MANAGER - FastAPI Microservice
# Puerto: 8002
# Funcionalidad: Consultas de historial clínico por paciente
# =============================================================================

# requirements.txt
"""
fastapi==0.104.1
uvicorn==0.24.0
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
python-decouple==3.8
python-multipart==0.0.6
pydantic==2.5.0
"""

# =============================================================================
# main.py
# =============================================================================

from fastapi import FastAPI, HTTPException, Depends, Query
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UUID, Date, DECIMAL
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, date
from decouple import config
import logging
import uuid

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/history_clinic_manager/logs/history_clinic.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("history_clinic_manager")

# Configuración de base de datos
DATABASE_URL = f"postgresql://{config('DB_USER', default='postgres')}:{config('DB_PASSWORD', default='postgres123')}@{config('DB_HOST', default='10.128.0.5')}:{config('DB_PORT', default='5432')}/{config('DB_NAME', default='patients_db')}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================================================================
# Modelos SQLAlchemy (coinciden con Django models)
# =============================================================================

class Patient(Base):
    __tablename__ = "patients_patient"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(UUID, unique=True, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    date_of_birth = Column(Date)
    gender = Column(String(1))
    email = Column(String, unique=True, index=True)
    phone = Column(String(17))
    address = Column(Text)
    city = Column(String(100))
    state = Column(String(100))
    zip_code = Column(String(10))
    country = Column(String(100))
    blood_type = Column(String(3))
    height = Column(DECIMAL(5, 2))
    weight = Column(DECIMAL(5, 2))
    allergies = Column(Text)
    medical_conditions = Column(Text)
    medications = Column(Text)
    emergency_contact_name = Column(String(200))
    emergency_contact_phone = Column(String(17))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    
    # Relación con medical records
    medical_records = relationship("MedicalRecord", back_populates="patient")

class MedicalRecord(Base):
    __tablename__ = "patients_medicalrecord"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients_patient.id"))
    visit_date = Column(DateTime)
    diagnosis = Column(Text)
    treatment = Column(Text)
    doctor_name = Column(String(200))
    notes = Column(Text)
    created_at = Column(DateTime)
    
    # Relación con patient
    patient = relationship("Patient", back_populates="medical_records")

# =============================================================================
# Modelos Pydantic para respuestas
# =============================================================================

class PatientBase(BaseModel):
    patient_id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str
    email: str
    phone: str
    city: str
    blood_type: str
    
    class Config:
        from_attributes = True

class MedicalRecordResponse(BaseModel):
    id: int
    visit_date: datetime
    diagnosis: str
    treatment: str
    doctor_name: str
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class PatientHistoryResponse(BaseModel):
    patient: PatientBase
    total_visits: int
    medical_records: List[MedicalRecordResponse]
    
    class Config:
        from_attributes = True

class HistoryStatsResponse(BaseModel):
    total_patients_with_history: int
    total_medical_records: int
    average_visits_per_patient: float
    most_common_diagnoses: List[dict]
    most_active_doctors: List[dict]

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="History Clinic Manager",
    description="Microservicio para consultas de historial clínico",
    version="1.0.0"
)

# Dependency para obtener DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health/", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "history_clinic_manager",
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }

@app.get("/history/patient/{patient_id}", response_model=PatientHistoryResponse, tags=["History"])
async def get_patient_history(
    patient_id: str,
    limit: int = Query(10, ge=1, le=100, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """Obtener historial completo de un paciente"""
    
    logger.info(f"Fetching history for patient: {patient_id}")
    
    try:
        # Buscar paciente por UUID o ID
        if len(patient_id) > 10:  # Probablemente es UUID
            patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
        else:  # Probablemente es ID numérico
            patient = db.query(Patient).filter(Patient.id == int(patient_id)).first()
        
        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
        # Obtener registros médicos
        medical_records = db.query(MedicalRecord)\
                           .filter(MedicalRecord.patient_id == patient.id)\
                           .order_by(MedicalRecord.visit_date.desc())\
                           .limit(limit)\
                           .all()
        
        total_visits = db.query(MedicalRecord)\
                        .filter(MedicalRecord.patient_id == patient.id)\
                        .count()
        
        logger.info(f"Found {len(medical_records)} records for patient {patient.first_name} {patient.last_name}")
        
        return PatientHistoryResponse(
            patient=PatientBase.from_orm(patient),
            total_visits=total_visits,
            medical_records=[MedicalRecordResponse.from_orm(record) for record in medical_records]
        )
        
    except ValueError:
        logger.error(f"Invalid patient ID format: {patient_id}")
        raise HTTPException(status_code=400, detail="Formato de ID de paciente inválido")
    except Exception as e:
        logger.error(f"Error fetching patient history: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")

@app.get("/history/search/", tags=["History"])
async def search_patient_history(
    query: str = Query(..., min_length=2, description="Término de búsqueda"),
    limit: int = Query(10, ge=1, le=50, description="Límite de resultados"),
    db: Session = Depends(get_db)
):
    """Buscar pacientes por nombre, email o diagnóstico"""
    
    logger.info(f"Searching patients with query: {query}")
    
    try:
        # Buscar en información del paciente
        patients_query = db.query(Patient).filter(
            (Patient.first_name.ilike(f"%{query}%")) |
            (Patient.last_name.ilike(f"%{query}%")) |
            (Patient.email.ilike(f"%{query}%"))
        ).filter(Patient.is_active == True)
        
        # También buscar por diagnóstico
        patients_by_diagnosis = db.query(Patient).join(MedicalRecord).filter(
            MedicalRecord.diagnosis.ilike(f"%{query}%")
        ).filter(Patient.is_active == True)
        
        # Combinar resultados
        all_patients = patients_query.union(patients_by_diagnosis).limit(limit).all()
        
        results = []
        for patient in all_patients:
            recent_records = db.query(MedicalRecord)\
                              .filter(MedicalRecord.patient_id == patient.id)\
                              .order_by(MedicalRecord.visit_date.desc())\
                              .limit(3)\
                              .all()
            
            results.append({
                "patient": PatientBase.from_orm(patient),
                "recent_visits": len(recent_records),
                "last_visit": recent_records[0].visit_date if recent_records else None,
                "recent_diagnosis": recent_records[0].diagnosis if recent_records else None
            })
        
        logger.info(f"Found {len(results)} patients matching query: {query}")
        return {"results": results, "total": len(results)}
        
    except Exception as e:
        logger.error(f"Error searching patients: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en la búsqueda")

@app.get("/history/timeline/{patient_id}", tags=["History"])
async def get_patient_timeline(
    patient_id: str,
    start_date: Optional[date] = Query(None, description="Fecha inicio (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="Fecha fin (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """Obtener timeline cronológico de un paciente"""
    
    logger.info(f"Fetching timeline for patient: {patient_id}")
    
    try:
        # Buscar paciente
        if len(patient_id) > 10:
            patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
        else:
            patient = db.query(Patient).filter(Patient.id == int(patient_id)).first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
        # Construir query con filtros de fecha
        query = db.query(MedicalRecord).filter(MedicalRecord.patient_id == patient.id)
        
        if start_date:
            query = query.filter(MedicalRecord.visit_date >= start_date)
        if end_date:
            query = query.filter(MedicalRecord.visit_date <= end_date)
        
        records = query.order_by(MedicalRecord.visit_date.asc()).all()
        
        timeline = []
        for record in records:
            timeline.append({
                "date": record.visit_date.date(),
                "doctor": record.doctor_name,
                "diagnosis": record.diagnosis,
                "treatment": record.treatment,
                "notes": record.notes
            })
        
        logger.info(f"Generated timeline with {len(timeline)} entries for patient {patient.first_name} {patient.last_name}")
        
        return {
            "patient": PatientBase.from_orm(patient),
            "timeline": timeline,
            "period": {
                "start_date": start_date,
                "end_date": end_date,
                "total_entries": len(timeline)
            }
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de ID de paciente inválido")
    except Exception as e:
        logger.error(f"Error generating timeline: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generando timeline")

@app.get("/history/stats/", response_model=HistoryStatsResponse, tags=["Statistics"])
async def get_history_statistics(db: Session = Depends(get_db)):
    """Obtener estadísticas generales del historial clínico"""
    
    logger.info("Fetching history statistics")
    
    try:
        # Estadísticas básicas
        total_patients = db.query(Patient).filter(Patient.is_active == True).count()
        total_records = db.query(MedicalRecord).count()
        patients_with_history = db.query(Patient).join(MedicalRecord).distinct().count()
        
        avg_visits = total_records / max(patients_with_history, 1)
        
        # Diagnósticos más comunes
        from sqlalchemy import func
        common_diagnoses = db.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.diagnosis).label('count')
        ).group_by(MedicalRecord.diagnosis)\
         .order_by(func.count(MedicalRecord.diagnosis).desc())\
         .limit(10)\
         .all()
        
        # Doctores más activos
        active_doctors = db.query(
            MedicalRecord.doctor_name,
            func.count(MedicalRecord.doctor_name).label('count')
        ).group_by(MedicalRecord.doctor_name)\
         .order_by(func.count(MedicalRecord.doctor_name).desc())\
         .limit(10)\
         .all()
        
        stats = HistoryStatsResponse(
            total_patients_with_history=patients_with_history,
            total_medical_records=total_records,
            average_visits_per_patient=round(avg_visits, 2),
            most_common_diagnoses=[{"diagnosis": d.diagnosis, "count": d.count} for d in common_diagnoses],
            most_active_doctors=[{"doctor": d.doctor_name, "count": d.count} for d in active_doctors]
        )
        
        logger.info(f"Generated statistics: {patients_with_history} patients with history, {total_records} total records")
        return stats
        
    except Exception as e:
        logger.error(f"Error generating statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generando estadísticas")

# =============================================================================
# Startup event
# =============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("History Clinic Manager starting up...")
    logger.info(f"Database URL: {DATABASE_URL.replace(config('DB_PASSWORD', default='postgres123'), '***')}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)