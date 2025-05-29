# =============================================================================
# DIAGNOSIS MANAGER - FastAPI Microservice
# Puerto: 8003
# Funcionalidad: Análisis y estadísticas de diagnósticos
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
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UUID, Date, DECIMAL, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decouple import config
import logging
from collections import Counter
import re

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/opt/diagnosis_manager/logs/diagnosis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("diagnosis_manager")

# Configuración de base de datos
DATABASE_URL = f"postgresql://{config('DB_USER', default='postgres')}:{config('DB_PASSWORD', default='postgres123')}@{config('DB_HOST', default='10.128.0.5')}:{config('DB_PORT', default='5432')}/{config('DB_NAME', default='patients_db')}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =============================================================================
# Modelos SQLAlchemy
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
    
    patient = relationship("Patient", back_populates="medical_records")

# =============================================================================
# Modelos Pydantic
# =============================================================================

class DiagnosisStatsResponse(BaseModel):
    total_diagnoses: int
    unique_diagnoses: int
    most_common_diagnoses: List[Dict[str, Any]]
    diagnosis_by_gender: Dict[str, int]
    diagnosis_by_age_group: Dict[str, int]
    diagnosis_trends: List[Dict[str, Any]]

class DiagnosisAnalysisResponse(BaseModel):
    diagnosis: str
    total_cases: int
    patients_affected: int
    age_distribution: Dict[str, int]
    gender_distribution: Dict[str, int]
    common_treatments: List[Dict[str, Any]]
    outcome_patterns: Dict[str, Any]

class RiskAssessmentResponse(BaseModel):
    patient_id: str
    patient_name: str
    risk_factors: List[str]
    risk_score: float
    recommendations: List[str]
    similar_cases: int
    
class TrendAnalysisResponse(BaseModel):
    period: str
    diagnosis_trends: List[Dict[str, Any]]
    seasonal_patterns: Dict[str, Any]
    emerging_conditions: List[str]
    declining_conditions: List[str]

# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(
    title="Diagnosis Manager",
    description="Microservicio para análisis y estadísticas de diagnósticos",
    version="1.0.0"
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =============================================================================
# Funciones auxiliares
# =============================================================================

def calculate_age(birth_date: date) -> int:
    """Calcular edad a partir de fecha de nacimiento"""
    today = date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def get_age_group(age: int) -> str:
    """Obtener grupo etario"""
    if age < 18:
        return "Menores de 18"
    elif age < 30:
        return "18-29"
    elif age < 50:
        return "30-49"
    elif age < 65:
        return "50-64"
    else:
        return "65+"

def extract_key_terms(diagnosis: str) -> List[str]:
    """Extraer términos clave de un diagnóstico"""
    # Términos médicos comunes para agrupar diagnósticos similares
    common_terms = [
        'hypertension', 'diabetes', 'asthma', 'arthritis', 'migraine',
        'depression', 'anxiety', 'allergic', 'bronchitis', 'gastritis',
        'dermatitis', 'insomnia', 'pain', 'infection', 'inflammation'
    ]
    
    diagnosis_lower = diagnosis.lower()
    found_terms = []
    
    for term in common_terms:
        if term in diagnosis_lower:
            found_terms.append(term.title())
    
    return found_terms if found_terms else [diagnosis.split()[0].title()]

# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health/", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "service": "diagnosis_manager",
        "timestamp": datetime.now(),
        "version": "1.0.0"
    }

@app.get("/diagnosis/stats/", response_model=DiagnosisStatsResponse, tags=["Statistics"])
async def get_diagnosis_statistics(
    days: int = Query(30, ge=1, le=365, description="Días hacia atrás para analizar"),
    db: Session = Depends(get_db)
):
    """Obtener estadísticas generales de diagnósticos"""
    
    logger.info(f"Fetching diagnosis statistics for last {days} days")
    
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Estadísticas básicas
        total_diagnoses = db.query(MedicalRecord).filter(
            MedicalRecord.visit_date >= cutoff_date
        ).count()
        
        unique_diagnoses = db.query(MedicalRecord.diagnosis).filter(
            MedicalRecord.visit_date >= cutoff_date
        ).distinct().count()
        
        # Diagnósticos más comunes
        common_diagnoses = db.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.diagnosis).label('count')
        ).filter(MedicalRecord.visit_date >= cutoff_date)\
         .group_by(MedicalRecord.diagnosis)\
         .order_by(func.count(MedicalRecord.diagnosis).desc())\
         .limit(10)\
         .all()
        
        # Diagnósticos por género
        gender_stats = db.query(
            Patient.gender,
            func.count(MedicalRecord.id).label('count')
        ).join(MedicalRecord)\
         .filter(MedicalRecord.visit_date >= cutoff_date)\
         .group_by(Patient.gender)\
         .all()
        
        # Diagnósticos por grupo etario
        patients_with_records = db.query(Patient, MedicalRecord)\
                                 .join(MedicalRecord)\
                                 .filter(MedicalRecord.visit_date >= cutoff_date)\
                                 .all()
        
        age_groups = {}
        for patient, record in patients_with_records:
            age = calculate_age(patient.date_of_birth)
            age_group = get_age_group(age)
            age_groups[age_group] = age_groups.get(age_group, 0) + 1
        
        # Tendencias por mes
        monthly_trends = db.query(
            func.date_trunc('month', MedicalRecord.visit_date).label('month'),
            func.count(MedicalRecord.id).label('count')
        ).filter(MedicalRecord.visit_date >= cutoff_date)\
         .group_by(func.date_trunc('month', MedicalRecord.visit_date))\
         .order_by(func.date_trunc('month', MedicalRecord.visit_date))\
         .all()
        
        stats = DiagnosisStatsResponse(
            total_diagnoses=total_diagnoses,
            unique_diagnoses=unique_diagnoses,
            most_common_diagnoses=[{"diagnosis": d.diagnosis, "count": d.count} for d in common_diagnoses],
            diagnosis_by_gender={g.gender: g.count for g in gender_stats},
            diagnosis_by_age_group=age_groups,
            diagnosis_trends=[{"month": t.month.strftime("%Y-%m"), "count": t.count} for t in monthly_trends]
        )
        
        logger.info(f"Generated statistics: {total_diagnoses} total diagnoses, {unique_diagnoses} unique")
        return stats
        
    except Exception as e:
        logger.error(f"Error generating diagnosis statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generando estadísticas")

@app.get("/diagnosis/analyze/{diagnosis}", response_model=DiagnosisAnalysisResponse, tags=["Analysis"])
async def analyze_diagnosis(
    diagnosis: str,
    exact_match: bool = Query(False, description="Búsqueda exacta o parcial"),
    db: Session = Depends(get_db)
):
    """Análisis detallado de un diagnóstico específico"""
    
    logger.info(f"Analyzing diagnosis: {diagnosis}")
    
    try:
        # Buscar registros médicos
        if exact_match:
            records = db.query(MedicalRecord).filter(
                MedicalRecord.diagnosis == diagnosis
            ).all()
        else:
            records = db.query(MedicalRecord).filter(
                MedicalRecord.diagnosis.ilike(f"%{diagnosis}%")
            ).all()
        
        if not records:
            raise HTTPException(status_code=404, detail="Diagnóstico no encontrado")
        
        # Obtener pacientes únicos
        patient_ids = list(set([r.patient_id for r in records]))
        patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
        
        # Análisis por edad
        age_distribution = {}
        for patient in patients:
            age = calculate_age(patient.date_of_birth)
            age_group = get_age_group(age)
            age_distribution[age_group] = age_distribution.get(age_group, 0) + 1
        
        # Análisis por género
        gender_distribution = {}
        for patient in patients:
            gender = patient.gender
            gender_distribution[gender] = gender_distribution.get(gender, 0) + 1
        
        # Tratamientos más comunes
        treatments = [r.treatment for r in records if r.treatment]
        treatment_counter = Counter(treatments)
        common_treatments = [{"treatment": t, "count": c} for t, c in treatment_counter.most_common(5)]
        
        # Patrones de resultado (análisis básico basado en notas)
        outcome_patterns = {"positive_outcomes": 0, "ongoing_treatment": 0, "complications": 0}
        
        for record in records:
            if record.notes:
                notes_lower = record.notes.lower()
                if any(word in notes_lower for word in ['improved', 'better', 'recovered', 'healed']):
                    outcome_patterns["positive_outcomes"] += 1
                elif any(word in notes_lower for word in ['ongoing', 'continue', 'monitor', 'follow']):
                    outcome_patterns["ongoing_treatment"] += 1
                elif any(word in notes_lower for word in ['complication', 'worse', 'deteriorated', 'severe']):
                    outcome_patterns["complications"] += 1
        
        analysis = DiagnosisAnalysisResponse(
            diagnosis=diagnosis,
            total_cases=len(records),
            patients_affected=len(patient_ids),
            age_distribution=age_distribution,
            gender_distribution=gender_distribution,
            common_treatments=common_treatments,
            outcome_patterns=outcome_patterns
        )
        
        logger.info(f"Analysis completed: {len(records)} cases, {len(patient_ids)} patients")
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing diagnosis: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en el análisis")

@app.get("/diagnosis/risk-assessment/{patient_id}", response_model=RiskAssessmentResponse, tags=["Risk Assessment"])
async def assess_patient_risk(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """Evaluación de riesgo para un paciente específico"""
    
    logger.info(f"Assessing risk for patient: {patient_id}")
    
    try:
        # Buscar paciente
        if len(patient_id) > 10:
            patient = db.query(Patient).filter(Patient.patient_id == patient_id).first()
        else:
            patient = db.query(Patient).filter(Patient.id == int(patient_id)).first()
        
        if not patient:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")
        
        # Obtener historial médico del paciente
        patient_records = db.query(MedicalRecord).filter(
            MedicalRecord.patient_id == patient.id
        ).order_by(MedicalRecord.visit_date.desc()).all()
        
        # Factores de riesgo
        risk_factors = []
        risk_score = 0.0
        
        # Edad
        age = calculate_age(patient.date_of_birth)
        if age > 65:
            risk_factors.append(f"Edad avanzada ({age} años)")
            risk_score += 1.5
        elif age > 50:
            risk_score += 0.5
        
        # Condiciones médicas previas
        if patient.medical_conditions:
            risk_factors.append("Condiciones médicas preexistentes")
            risk_score += 1.0
        
        # Alergias
        if patient.allergies:
            risk_factors.append("Alergias conocidas")
            risk_score += 0.5
        
        # Análisis de diagnósticos recientes
        recent_diagnoses = [r.diagnosis for r in patient_records[:5]]
        high_risk_conditions = ['diabetes', 'hypertension', 'heart', 'cancer', 'stroke']
        
        for diagnosis in recent_diagnoses:
            diagnosis_lower = diagnosis.lower()
            for condition in high_risk_conditions:
                if condition in diagnosis_lower:
                    risk_factors.append(f"Diagnóstico de alto riesgo: {diagnosis}")
                    risk_score += 2.0
                    break
        
        # Frecuencia de visitas
        if len(patient_records) > 10:
            risk_factors.append("Alta frecuencia de consultas médicas")
            risk_score += 1.0
        
        # Buscar casos similares
        similar_cases = 0
        if patient_records:
            latest_diagnosis = patient_records[0].diagnosis
            similar_cases = db.query(MedicalRecord).filter(
                MedicalRecord.diagnosis.ilike(f"%{latest_diagnosis.split()[0]}%"),
                MedicalRecord.patient_id != patient.id
            ).count()
        
        # Recomendaciones basadas en factores de riesgo
        recommendations = []
        if risk_score > 3.0:
            recommendations.extend([
                "Seguimiento médico frecuente recomendado",
                "Considerar evaluación preventiva especializada",
                "Monitoreo regular de signos vitales"
            ])
        elif risk_score > 1.5:
            recommendations.extend([
                "Chequeos médicos regulares",
                "Mantener estilo de vida saludable"
            ])
        else:
            recommendations.append("Continuar con chequeos médicos de rutina")
        
        if age > 50:
            recommendations.append("Considerar exámenes preventivos apropiados para la edad")
        
        assessment = RiskAssessmentResponse(
            patient_id=str(patient.patient_id),
            patient_name=f"{patient.first_name} {patient.last_name}",
            risk_factors=risk_factors,
            risk_score=round(risk_score, 2),
            recommendations=recommendations,
            similar_cases=similar_cases
        )
        
        logger.info(f"Risk assessment completed for {patient.first_name} {patient.last_name}: score {risk_score}")
        return assessment
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato de ID de paciente inválido")
    except Exception as e:
        logger.error(f"Error in risk assessment: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en evaluación de riesgo")

@app.get("/diagnosis/trends/", response_model=TrendAnalysisResponse, tags=["Trends"])
async def analyze_diagnosis_trends(
    months: int = Query(6, ge=1, le=24, description="Meses hacia atrás para analizar"),
    db: Session = Depends(get_db)
):
    """Análisis de tendencias de diagnósticos"""
    
    logger.info(f"Analyzing diagnosis trends for last {months} months")
    
    try:
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        
        # Tendencias mensuales por diagnóstico
        monthly_data = db.query(
            func.date_trunc('month', MedicalRecord.visit_date).label('month'),
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('count')
        ).filter(MedicalRecord.visit_date >= cutoff_date)\
         .group_by(func.date_trunc('month', MedicalRecord.visit_date), MedicalRecord.diagnosis)\
         .order_by(func.date_trunc('month', MedicalRecord.visit_date))\
         .all()
        
        # Procesar datos para identificar tendencias
        diagnosis_trends = {}
        for entry in monthly_data:
            month_str = entry.month.strftime("%Y-%m")
            if entry.diagnosis not in diagnosis_trends:
                diagnosis_trends[entry.diagnosis] = {}
            diagnosis_trends[entry.diagnosis][month_str] = entry.count
        
        # Identificar diagnósticos emergentes y en declive
        emerging_conditions = []
        declining_conditions = []
        
        for diagnosis, monthly_counts in diagnosis_trends.items():
            if len(monthly_counts) >= 3:  # Necesitamos al menos 3 meses de datos
                values = list(monthly_counts.values())
                if len(values) >= 3:
                    # Tendencia creciente
                    if values[-1] > values[0] and values[-1] > values[-2]:
                        emerging_conditions.append(diagnosis)
                    # Tendencia decreciente
                    elif values[-1] < values[0] and values[-1] < values[-2]:
                        declining_conditions.append(diagnosis)
        
        # Análisis estacional básico (por mes del año)
        seasonal_patterns = {}
        seasonal_data = db.query(
            func.extract('month', MedicalRecord.visit_date).label('month'),
            func.count(MedicalRecord.id).label('count')
        ).filter(MedicalRecord.visit_date >= cutoff_date)\
         .group_by(func.extract('month', MedicalRecord.visit_date))\
         .all()
        
        month_names = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                      'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        
        for entry in seasonal_data:
            month_name = month_names[int(entry.month) - 1]
            seasonal_patterns[month_name] = entry.count
        
        # Top diagnósticos con tendencias
        top_trends = []
        for diagnosis, monthly_counts in list(diagnosis_trends.items())[:10]:
            trend_data = {
                "diagnosis": diagnosis,
                "monthly_data": monthly_counts,
                "total_cases": sum(monthly_counts.values()),
                "trend": "stable"
            }
            
            if diagnosis in emerging_conditions:
                trend_data["trend"] = "increasing"
            elif diagnosis in declining_conditions:
                trend_data["trend"] = "decreasing"
            
            top_trends.append(trend_data)
        
        analysis = TrendAnalysisResponse(
            period=f"Last {months} months",
            diagnosis_trends=top_trends,
            seasonal_patterns=seasonal_patterns,
            emerging_conditions=emerging_conditions[:5],
            declining_conditions=declining_conditions[:5]
        )
        
        logger.info(f"Trends analysis completed: {len(emerging_conditions)} emerging, {len(declining_conditions)} declining")
        return analysis
        
    except Exception as e:
        logger.error(f"Error analyzing trends: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en análisis de tendencias")

@app.get("/diagnosis/compare/", tags=["Comparison"])
async def compare_diagnoses(
    diagnosis1: str = Query(..., description="Primer diagnóstico"),
    diagnosis2: str = Query(..., description="Segundo diagnóstico"),
    db: Session = Depends(get_db)
):
    """Comparar dos diagnósticos"""
    
    logger.info(f"Comparing diagnoses: {diagnosis1} vs {diagnosis2}")
    
    try:
        # Obtener datos para ambos diagnósticos
        records1 = db.query(MedicalRecord).filter(
            MedicalRecord.diagnosis.ilike(f"%{diagnosis1}%")
        ).all()
        
        records2 = db.query(MedicalRecord).filter(
            MedicalRecord.diagnosis.ilike(f"%{diagnosis2}%")
        ).all()
        
        if not records1 or not records2:
            raise HTTPException(status_code=404, detail="Uno o ambos diagnósticos no encontrados")
        
        def analyze_diagnosis_data(records):
            patient_ids = list(set([r.patient_id for r in records]))
            patients = db.query(Patient).filter(Patient.id.in_(patient_ids)).all()
            
            # Distribución por edad
            age_groups = {}
            for patient in patients:
                age = calculate_age(patient.date_of_birth)
                age_group = get_age_group(age)
                age_groups[age_group] = age_groups.get(age_group, 0) + 1
            
            # Distribución por género
            gender_dist = {}
            for patient in patients:
                gender_dist[patient.gender] = gender_dist.get(patient.gender, 0) + 1
            
            return {
                "total_cases": len(records),
                "unique_patients": len(patient_ids),
                "age_distribution": age_groups,
                "gender_distribution": gender_dist,
                "avg_age": sum([calculate_age(p.date_of_birth) for p in patients]) / len(patients) if patients else 0
            }
        
        analysis1 = analyze_diagnosis_data(records1)
        analysis2 = analyze_diagnosis_data(records2)
        
        comparison = {
            "diagnosis1": {
                "name": diagnosis1,
                "analysis": analysis1
            },
            "diagnosis2": {
                "name": diagnosis2,
                "analysis": analysis2
            },
            "comparison_metrics": {
                "prevalence_ratio": analysis1["total_cases"] / max(analysis2["total_cases"], 1),
                "age_difference": abs(analysis1["avg_age"] - analysis2["avg_age"]),
                "common_age_groups": list(set(analysis1["age_distribution"].keys()) & set(analysis2["age_distribution"].keys()))
            }
        }
        
        logger.info(f"Comparison completed: {analysis1['total_cases']} vs {analysis2['total_cases']} cases")
        return comparison
        
    except Exception as e:
        logger.error(f"Error comparing diagnoses: {str(e)}")
        raise HTTPException(status_code=500, detail="Error en la comparación")

# =============================================================================
# Startup event
# =============================================================================

@app.on_event("startup")
async def startup_event():
    logger.info("Diagnosis Manager starting up...")
    logger.info(f"Database URL: {DATABASE_URL.replace(config('DB_PASSWORD', default='postgres123'), '***')}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)