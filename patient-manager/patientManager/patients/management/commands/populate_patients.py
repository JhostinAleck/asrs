
import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from patients.models import Patient, MedicalRecord
from datetime import datetime, timedelta

class Command(BaseCommand):
    help = 'Populate database with fake patient data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--patients',
            type=int,
            default=1000,
            help='Number of patients to create (default: 1000)'
        )
        parser.add_argument(
            '--records',
            type=int,
            default=5000,
            help='Number of medical records to create (default: 5000)'
        )

    def handle(self, *args, **options):
        fake = Faker('es_CO') # Spanish and English locales
        
        patients_count = options['patients']
        records_count = options['records']
        
        self.stdout.write(f"Creating {patients_count} patients and {records_count} medical records...")
        
        estados = ['Colombia', 'España', 'Estados Unidos', 'México']
        ciudades = ['Cundinamarca', 'Boyaca', 'Huila', 'Narino']
        # Create patients
        patients = []
        for i in range(patients_count):
            patient = Patient(
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=90),
                gender=random.choice(['M', 'F', 'O']),
                email=fake.unique.email(),
                phone=fake.phone_number()[:17],
                address=fake.address(),
                city=fake.city(),
                state=random.choice(ciudades),
                zip_code=fake.postcode()[:10],
                country=random.choice(estados),
                blood_type=random.choice(['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']),
                height=round(random.uniform(150.0, 200.0), 2),
                weight=round(random.uniform(50.0, 120.0), 2),
                allergies=fake.text(max_nb_chars=200) if random.random() > 0.7 else None,
                medical_conditions=fake.text(max_nb_chars=300) if random.random() > 0.6 else None,
                medications=fake.text(max_nb_chars=200) if random.random() > 0.5 else None,
                emergency_contact_name=fake.name(),
                emergency_contact_phone=fake.phone_number()[:17],
            )
            patients.append(patient)
            
            if (i + 1) % 100 == 0:
                self.stdout.write(f"Prepared {i + 1} patients...")
        
        # Bulk create patients
        Patient.objects.bulk_create(patients, batch_size=100)
        self.stdout.write(self.style.SUCCESS(f"Created {patients_count} patients"))
        
        # Get created patients for medical records
        all_patients = list(Patient.objects.all())
        
        # Create medical records
        medical_records = []
        diagnoses = [
            "Hipertensión", "Diabetes tipo 2", "Gripa común", "Migraña",
            "Trastorno de ansiedad", "Dolor de espalda", "Rinitis alérgica", "Asma",
            "Gastroenteritis", "Dermatitis", "Insomnio", "Depresión", "Artritis",
            "Bronquitis", "Sinusitis", "Infección urinaria"
        ]
        
        treatments = [
            "Medicamento prescrito y descanso",
            "Terapia física recomendada",
            "Cambio de estilo de vida sugerido",
            "Seguimiento en 2 semanas",
            "Referencia a especialista",
            "Examen de sangre ordenado",
            "Examen de rayos X",
            "Modificaciones dietéticas",
            "Programa de ejercicio iniciado",
            "Técnicas de manejo del estrés"
        ]
        
        doctors = [
            "Dr. María González", "Dr. Carlos Rodríguez", "Dr. Ana Martínez",
            "Dr. Luis Hernández", "Dr. Carmen López", "Dr. José García",
            "Dr. Isabel Fernández", "Dr. Miguel Sánchez", "Dr. Laura Ruiz",
            "Dr. Antonio Jiménez"
        ]
        
        for i in range(records_count):
            patient = random.choice(all_patients)
            visit_date = fake.date_time_between(start_date='-2y', end_date='now', tzinfo=timezone.get_current_timezone())
            
            record = MedicalRecord(
                patient=patient,
                visit_date=visit_date,
                diagnosis=random.choice(diagnoses),
                treatment=random.choice(treatments),
                doctor_name=random.choice(doctors),
                notes=fake.text(max_nb_chars=500) if random.random() > 0.5 else None,
            )
            medical_records.append(record)
            
            if (i + 1) % 500 == 0:
                self.stdout.write(f"Prepared {i + 1} medical records...")
        
        # Bulk create medical records
        MedicalRecord.objects.bulk_create(medical_records, batch_size=100)
        self.stdout.write(self.style.SUCCESS(f"Created {records_count} medical records"))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully populated database with {patients_count} patients and {records_count} medical records'
            )
        )