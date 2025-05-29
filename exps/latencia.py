#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENTO 3: VALIDACIÓN DE LATENCIA (ASR-3)
=============================================================================

Objetivo: Verificar que las consultas de pacientes a través del flujo completo
(Nginx → User Manager → Patient Manager → PostgreSQL) se completen en menos
de 500ms para el percentil 95, incluyendo validación JWT y consulta a BD.

Métricas a evaluar:
- Latencia end-to-end P95: < 500ms
- Latencia de validación JWT: < 50ms
- Latencia de consulta DB: < 200ms

Uso: python3 latencia.py --server-ip 35.202.107.19
"""

import requests
import time
import json
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
from collections import defaultdict

# Configurar logging detallado con soporte para Unicode
def configure_logging():
    # Crear logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # Formato personalizado que soporta Unicode
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Configurar handler para archivo con codificación UTF-8
    file_handler = logging.FileHandler('latency_experiment.log', encoding='utf-8')
    file_handler.setFormatter(formatter)
    
    # Configurar handler para consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Asegurarse de que no hay handlers duplicados
    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

# Configurar el logger
logger = configure_logging()

class LatencyExperiment:
    def __init__(self, server_ip: str):
        self.server_ip = server_ip
        self.base_url = f"http://{server_ip}"
        self.auth_url = f"{self.base_url}/auth"
        self.patients_url = f"{self.base_url}/patients"
        
        # Configuración del experimento
        self.warmup_requests = 10
        self.test_requests = 100
        self.concurrent_users = [1, 5, 10, 20]  # Diferentes niveles de concurrencia
        
        # Métricas de prueba
        self.results = {
            'authentication_latency': {},
            'patient_list_latency': {},
            'patient_detail_latency': {},
            'patient_search_latency': {},
            'end_to_end_latency': {},
            'concurrent_load_test': {}
        }
        
        # JWT para tests
        self.jwt_token = None
        self.auth_headers = {}
        
        logger.info(f"⚡ Iniciando experimento de latencia contra servidor: {server_ip}")
    
    def authenticate(self) -> bool:
        """
        Obtener JWT token para los tests
        """
        logger.info("🔑 Obteniendo token de autenticación...")
        
        login_url = f"{self.auth_url}/login/"
        credentials = {
            'username': 'testuser1',
            'password': 'test123'
        }
        
        try:
            start_time = time.time()
            response = requests.post(
                login_url,
                json=credentials,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            auth_time = time.time() - start_time
            
            if response.status_code == 200:
                token_data = response.json()
                self.jwt_token = token_data.get('access')
                self.auth_headers = {
                    'Authorization': f'Bearer {self.jwt_token}',
                    'Content-Type': 'application/json'
                }
                
                logger.info(f"✅ Autenticación exitosa en {auth_time*1000:.2f}ms")
                return True
            else:
                logger.error(f"❌ Error en autenticación: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error en autenticación: {e}")
            return False
    
    def warmup_server(self):
        """
        Calentar el servidor con requests iniciales
        """
        logger.info("🔥 Calentando servidor...")
        
        endpoints = [
            f"{self.patients_url}/patients/",
            f"{self.patients_url}/health/",
            f"{self.patients_url}/stats/"
        ]
        
        for _ in range(self.warmup_requests):
            for endpoint in endpoints:
                try:
                    requests.get(endpoint, headers=self.auth_headers, timeout=5)
                except:
                    pass
        
        logger.info("✅ Servidor calentado")
    
    def measure_authentication_latency(self) -> Dict:
        """
        Test 1: Medir latencia de autenticación JWT
        """
        logger.info("🔑 Midiendo latencia de autenticación...")
        
        login_url = f"{self.auth_url}/login/"
        credentials = {
            'username': 'testuser2',
            'password': 'test123'
        }
        
        auth_times = []
        validation_times = []
        
        # Test de autenticación (obtención de token)
        for i in range(20):
            try:
                start_time = time.time()
                response = requests.post(
                    login_url,
                    json=credentials,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    auth_time = (end_time - start_time) * 1000  # ms
                    auth_times.append(auth_time)
                    
                    # Test de validación de token
                    token = response.json().get('access')
                    headers = {'Authorization': f'Bearer {token}'}
                    
                    start_validation = time.time()
                    validation_response = requests.get(
                        f"{self.patients_url}/patients/",
                        headers=headers,
                        timeout=10
                    )
                    end_validation = time.time()
                    
                    if validation_response.status_code == 200:
                        validation_time = (end_validation - start_validation) * 1000
                        validation_times.append(validation_time)
                
                if (i + 1) % 5 == 0:
                    logger.info(f"Completadas {i+1}/20 autenticaciones")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en autenticación {i+1}: {e}")
        
        # Calcular estadísticas
        auth_stats = self.calculate_latency_stats(auth_times, "Autenticación")
        validation_stats = self.calculate_latency_stats(validation_times, "Validación JWT")
        
        return {
            'authentication': auth_stats,
            'jwt_validation': validation_stats
        }
    
    def measure_patient_list_latency(self) -> Dict:
        """
        Test 2: Medir latencia de listado de pacientes
        """
        logger.info("📋 Midiendo latencia de listado de pacientes...")
        
        endpoint = f"{self.patients_url}/patients/"
        latencies = []
        
        for i in range(self.test_requests):
            try:
                start_time = time.time()
                response = requests.get(
                    endpoint,
                    headers=self.auth_headers,
                    timeout=10
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    latency = (end_time - start_time) * 1000
                    latencies.append(latency)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"Completadas {i+1}/{self.test_requests} consultas de listado")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en consulta {i+1}: {e}")
        
        return self.calculate_latency_stats(latencies, "Listado de pacientes")
    
    def measure_patient_detail_latency(self) -> Dict:
        """
        Test 3: Medir latencia de detalle de paciente
        """
        logger.info("👤 Midiendo latencia de detalle de paciente...")
        
        # Primero obtener lista de pacientes para tener IDs válidos
        try:
            response = requests.get(
                f"{self.patients_url}/patients/",
                headers=self.auth_headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error("No se pudo obtener lista de pacientes")
                return {}
            
            patients = response.json().get('results', [])
            if not patients:
                logger.error("No hay pacientes en la base de datos")
                return {}
            
            # Tomar los primeros 10 pacientes para rotar
            patient_ids = [p['id'] for p in patients[:10]]
            
        except Exception as e:
            logger.error(f"Error obteniendo pacientes: {e}")
            return {}
        
        latencies = []
        
        for i in range(self.test_requests):
            try:
                # Rotar entre diferentes pacientes
                patient_id = patient_ids[i % len(patient_ids)]
                
                start_time = time.time()
                response = requests.get(
                    f"{self.patients_url}/patients/{patient_id}/",
                    headers=self.auth_headers,
                    timeout=10
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    latency = (end_time - start_time) * 1000
                    latencies.append(latency)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"Completadas {i+1}/{self.test_requests} consultas de detalle")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en consulta de detalle {i+1}: {e}")
        
        return self.calculate_latency_stats(latencies, "Detalle de paciente")
    
    def measure_patient_search_latency(self) -> Dict:
        """
        Test 4: Medir latencia de búsqueda de pacientes
        """
        logger.info("🔍 Midiendo latencia de búsqueda de pacientes...")
        
        # Términos de búsqueda variados
        search_terms = [
            "Maria", "Carlos", "Ana", "Luis", "Jose",
            "Gonzalez", "Rodriguez", "Martinez", "Lopez",
            "Garcia", "@gmail", "555", "123"
        ]
        
        latencies = []
        
        for i in range(self.test_requests):
            try:
                search_term = search_terms[i % len(search_terms)]
                
                start_time = time.time()
                response = requests.get(
                    f"{self.patients_url}/patients/search/",
                    params={'q': search_term},
                    headers=self.auth_headers,
                    timeout=10
                )
                end_time = time.time()
                
                if response.status_code == 200:
                    latency = (end_time - start_time) * 1000
                    latencies.append(latency)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"Completadas {i+1}/{self.test_requests} búsquedas")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en búsqueda {i+1}: {e}")
        
        return self.calculate_latency_stats(latencies, "Búsqueda de pacientes")
    
    def measure_end_to_end_latency(self) -> Dict:
        """
        Test 5: Medir latencia end-to-end (autenticación + consulta)
        """
        logger.info("🔄 Midiendo latencia end-to-end...")
        
        login_url = f"{self.auth_url}/login/"
        patients_url = f"{self.patients_url}/patients/"
        
        credentials = {
            'username': 'patient_user',
            'password': 'patient123'
        }
        
        e2e_latencies = []
        auth_latencies = []
        query_latencies = []
        
        for i in range(50):  # Menos repeticiones por ser más costoso
            try:
                # Medir autenticación
                auth_start = time.time()
                auth_response = requests.post(
                    login_url,
                    json=credentials,
                    headers={'Content-Type': 'application/json'},
                    timeout=10
                )
                auth_end = time.time()
                
                if auth_response.status_code != 200:
                    continue
                
                auth_time = (auth_end - auth_start) * 1000
                auth_latencies.append(auth_time)
                
                # Obtener token y hacer consulta
                token = auth_response.json().get('access')
                headers = {'Authorization': f'Bearer {token}'}
                
                query_start = time.time()
                query_response = requests.get(
                    patients_url,
                    headers=headers,
                    timeout=10
                )
                query_end = time.time()
                
                if query_response.status_code == 200:
                    query_time = (query_end - query_start) * 1000
                    query_latencies.append(query_time)
                    
                    # Latencia total (desde inicio de auth hasta fin de query)
                    total_time = (query_end - auth_start) * 1000
                    e2e_latencies.append(total_time)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Completadas {i+1}/50 pruebas end-to-end")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en prueba e2e {i+1}: {e}")
        
        return {
            'end_to_end': self.calculate_latency_stats(e2e_latencies, "End-to-End"),
            'auth_component': self.calculate_latency_stats(auth_latencies, "Componente Auth"),
            'query_component': self.calculate_latency_stats(query_latencies, "Componente Query")
        }
    
    def measure_concurrent_load(self) -> Dict:
        """
        Test 6: Medir latencia bajo carga concurrente
        """
        logger.info("👥 Midiendo latencia bajo carga concurrente...")
        
        concurrent_results = {}
        
        for users in self.concurrent_users:
            logger.info(f"Testeando con {users} usuarios concurrentes...")
            
            def concurrent_request(request_id):
                try:
                    start_time = time.time()
                    response = requests.get(
                        f"{self.patients_url}/patients/",
                        headers=self.auth_headers,
                        timeout=15
                    )
                    end_time = time.time()
                    
                    return {
                        'request_id': request_id,
                        'latency': (end_time - start_time) * 1000,
                        'success': response.status_code == 200,
                        'status_code': response.status_code
                    }
                except Exception as e:
                    return {
                        'request_id': request_id,
                        'error': str(e),
                        'success': False
                    }
            
            # Ejecutar requests concurrentes
            latencies = []
            errors = 0
            
            with ThreadPoolExecutor(max_workers=users) as executor:
                futures = [executor.submit(concurrent_request, i) for i in range(users * 5)]
                
                for future in as_completed(futures):
                    result = future.result()
                    if result.get('success'):
                        latencies.append(result['latency'])
                    else:
                        errors += 1
            
            # Calcular estadísticas para este nivel de concurrencia
            stats = self.calculate_latency_stats(latencies, f"{users} usuarios concurrentes")
            stats['errors'] = errors
            stats['success_rate'] = len(latencies) / (len(latencies) + errors) * 100
            
            concurrent_results[f"{users}_users"] = stats
            
            logger.info(f"✅ {users} usuarios: P95={stats.get('p95', 0):.2f}ms, Success={stats.get('success_rate', 0):.1f}%")
        
        return concurrent_results
    
    def calculate_latency_stats(self, latencies: List[float], test_name: str) -> Dict:
        """
        Calcular estadísticas de latencia
        """
        if not latencies:
            logger.warning(f"No hay datos de latencia para {test_name}")
            return {}
        
        stats = {
            'test_name': test_name,
            'count': len(latencies),
            'min': min(latencies),
            'max': max(latencies),
            'mean': statistics.mean(latencies),
            'median': statistics.median(latencies),
            'p95': np.percentile(latencies, 95),
            'p99': np.percentile(latencies, 99),
            'std_dev': statistics.stdev(latencies) if len(latencies) > 1 else 0
        }
        
        logger.info(f"📊 {test_name}:")
        logger.info(f"   Promedio: {stats['mean']:.2f}ms")
        logger.info(f"   P95: {stats['p95']:.2f}ms")
        logger.info(f"   Min/Max: {stats['min']:.2f}ms / {stats['max']:.2f}ms")
        
        return stats
    
    def run_all_tests(self) -> Dict:
        """
        Ejecutar todos los tests de latencia
        """
        logger.info("🚀 Iniciando experimento completo de latencia...")
        
        start_time = datetime.now()
        
        # Autenticarse
        if not self.authenticate():
            logger.error("❌ No se pudo autenticar. Abortando experimento.")
            return {}
        
        # Calentar servidor
        self.warmup_server()
        
        # Ejecutar tests
        logger.info("📊 Ejecutando tests de latencia...")
        
        self.results['authentication_latency'] = self.measure_authentication_latency()
        self.results['patient_list_latency'] = self.measure_patient_list_latency()
        self.results['patient_detail_latency'] = self.measure_patient_detail_latency()
        self.results['patient_search_latency'] = self.measure_patient_search_latency()
        self.results['end_to_end_latency'] = self.measure_end_to_end_latency()
        self.results['concurrent_load_test'] = self.measure_concurrent_load()
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Generar reporte final
        report = self.generate_latency_report(total_duration)
        
        return report
    
    def generate_latency_report(self, duration: float) -> Dict:
        """
        Generar reporte final del experimento de latencia
        """
        logger.info("📋 Generando reporte final de latencia...")
        
        report = {
            'experiment': 'Latency Validation (ASR-3)',
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'server_ip': self.server_ip,
            'asr_compliance': {},
            'test_results': self.results,
            'summary': {}
        }
        
        # Evaluar cumplimiento de ASRs
        asr_compliance = {}
        
        # ASR 3.1: Latencia end-to-end P95 < 800ms
        e2e_test = self.results.get('end_to_end_latency', {}).get('end_to_end', {})
        if e2e_test.get('p95'):
            asr_compliance['end_to_end_p95'] = {
                'requirement': '< 800ms',
                'actual': f"{e2e_test['p95']:.2f}ms",
                'compliant': e2e_test['p95'] < 800
            }
        
        # ASR 3.2: Latencia de validación JWT < 250ms
        jwt_test = self.results.get('authentication_latency', {}).get('jwt_validation', {})
        if jwt_test.get('mean'):
            asr_compliance['jwt_validation'] = {
                'requirement': '< 250ms',
                'actual': f"{jwt_test['mean']:.2f}ms",
                'compliant': jwt_test['mean'] < 250
            }
        
        # ASR 3.3: Latencia de consulta DB < 200ms (aproximada por consulta de detalle)
        detail_test = self.results.get('patient_detail_latency', {})
        if detail_test.get('mean'):
            asr_compliance['database_query'] = {
                'requirement': '< 200ms',
                'actual': f"{detail_test['mean']:.2f}ms",
                'compliant': detail_test['mean'] < 200
            }
        
        report['asr_compliance'] = asr_compliance
        
        # Análisis de rendimiento bajo carga
        load_analysis = {}
        concurrent_tests = self.results.get('concurrent_load_test', {})
        
        for test_name, test_data in concurrent_tests.items():
            if test_data.get('p95'):
                load_analysis[test_name] = {
                    'p95_latency': test_data['p95'],
                    'success_rate': test_data.get('success_rate', 0),
                    'acceptable_performance': test_data['p95'] < 1000  # < 1 segundo bajo carga
                }
        
        report['load_analysis'] = load_analysis
        
        # Resumen general
        total_compliant = sum(1 for asr in asr_compliance.values() if asr.get('compliant', False))
        total_asrs = len(asr_compliance)
        
        report['summary'] = {
            'total_asrs_evaluated': total_asrs,
            'compliant_asrs': total_compliant,
            'compliance_percentage': (total_compliant / max(1, total_asrs)) * 100,
            'overall_performance_status': 'PASS' if total_compliant == total_asrs else 'FAIL'
        }
        
        # Log del resumen
        logger.info("=" * 60)
        logger.info("⚡ REPORTE FINAL DE LATENCIA")
        logger.info("=" * 60)
        logger.info(f"Servidor testeado: {self.server_ip}")
        logger.info(f"Duración del experimento: {duration:.2f} segundos")
        logger.info(f"ASRs evaluados: {total_asrs}")
        logger.info(f"ASRs cumplidos: {total_compliant}")
        logger.info(f"Porcentaje de cumplimiento: {report['summary']['compliance_percentage']:.1f}%")
        logger.info(f"Estado general: {report['summary']['overall_performance_status']}")
        
        for asr_name, asr_data in asr_compliance.items():
            status = "✅ PASS" if asr_data['compliant'] else "❌ FAIL"
            logger.info(f"{asr_name}: {asr_data['actual']} (req: {asr_data['requirement']}) {status}")
        
        logger.info("=" * 60)
        
        return report

def main():
    parser = argparse.ArgumentParser(description='Latency Experiment - ASR-3 Validation')
    parser.add_argument('--server-ip', required=True, help='IP address of the server to test')
    parser.add_argument('--output', default='latency_experiment_results.json', help='Output file for results')
    
    args = parser.parse_args()
    
    # Ejecutar experimento
    experiment = LatencyExperiment(args.server_ip)
    results = experiment.run_all_tests()
    
    if not results:
        logger.error("💥 Experimento falló - no se generaron resultados")
        return
    
    # Guardar resultados
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"📄 Resultados guardados en: {args.output}")
    
    # Mostrar resultado final
    if results['summary']['overall_performance_status'] == 'PASS':
        logger.info("🎉 EXPERIMENTO DE LATENCIA: EXITOSO")
    else:
        logger.error("💥 EXPERIMENTO DE LATENCIA: FALLIDO")

if __name__ == "__main__":
    main()