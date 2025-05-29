#!/usr/bin/env python3
"""
=============================================================================
EXPERIMENTO 2: VALIDACIÓN DE SEGURIDAD (ASR-2)
=============================================================================

Objetivo: Verificar que el sistema previene ataques de fuerza bruta
bloqueando automáticamente IPs después de 5 intentos fallidos en 5 minutos,
y que todos los endpoints requieren autenticación JWT válida.

Métricas a evaluar:
- Tiempo de detección de ataque de fuerza bruta: < 1 segundo
- Tasa de falsos positivos en bloqueo de IPs: < 0.1%
- Tiempo de validación JWT: < 250ms

Uso: python3 seguridad.py --server-ip  35.202.107.19
"""

import requests
import time
import json
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Tuple
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configurar logging detallado
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Formato para los logs
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# Handler para archivo (maneja Unicode correctamente)
file_handler = logging.FileHandler('security_experiment.log', encoding='utf-8')
file_handler.setFormatter(formatter)

# Handler para consola (con soporte para Unicode en Windows)
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Configurar la codificación para la consola de Windows
import sys
if sys.platform == 'win32':
    import io
    import sys
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if isinstance(sys.stderr, io.TextIOWrapper):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Añadir handlers al logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

class SecurityExperiment:
    def __init__(self, server_ip: str):
        self.server_ip = server_ip
        self.base_url = f"http://{server_ip}"
        self.auth_url = f"{self.base_url}/auth"
        self.patients_url = f"{self.base_url}/patients"
        
        # Métricas de prueba
        self.results = {
            'brute_force_test': {},
            'jwt_validation_test': {},
            'endpoint_protection_test': {},
            'dos_prevention_test': {}
        }
        
        # Configuración de timeouts
        self.request_timeout = 10
        
        logger.info(f" Iniciando experimento de seguridad contra servidor: {server_ip}")
    
    def test_brute_force_protection(self) -> Dict:
        """
        Test 1: Verificar protección contra ataques de fuerza bruta
        """
        logger.info(" Iniciando test de protección contra fuerza bruta...")
        
        test_results = {
            'blocked_after_attempts': False,
            'block_time': None,
            'detection_times': [],
            'false_positives': 0,
            'total_attempts': 0
        }
        
        # Credenciales incorrectas para el test
        wrong_credentials = {
            'username': 'hacker_attempt',
            'password': 'wrong_password_123'
        }
        
        login_url = f"{self.auth_url}/login/"
        attempts_times = []
        
        logger.info("Realizando intentos de login fallidos...")
        
        # Realizar 6 intentos fallidos (debería bloquear después del 5to)
        for attempt in range(1, 7):
            start_time = time.time()
            
            try:
                response = requests.post(
                    login_url,
                    json=wrong_credentials,
                    headers={'Content-Type': 'application/json'},
                    timeout=self.request_timeout
                )
                
                end_time = time.time()
                response_time = end_time - start_time
                attempts_times.append(response_time)
                
                logger.info(f"Intento {attempt}: Status {response.status_code}, Tiempo: {response_time:.3f}s")
                
                test_results['total_attempts'] = attempt
                
                # Verificar si fue bloqueado (código 429 = Too Many Requests)
                if response.status_code == 429:
                    test_results['blocked_after_attempts'] = True
                    test_results['block_time'] = response_time
                    
                    logger.warning(f" IP bloqueada después de {attempt} intentos")
                    logger.info(f"Respuesta del servidor: {response.text}")
                    
                    # Verificar tiempo de detección
                    if response_time < 1.0:  # Debe ser < 1 segundo
                        test_results['detection_times'].append(response_time)
                        logger.info(f" Tiempo de detección: {response_time:.3f}s (< 1s)")
                    else:
                        logger.error(f" Tiempo de detección lento: {response_time:.3f}s (> 1s)")
                    
                    break
                
                elif response.status_code == 401:
                    logger.info(f"Intento {attempt} rechazado correctamente (401 Unauthorized)")
                else:
                    logger.warning(f"Respuesta inesperada: {response.status_code}")
                
                # Esperar un poco entre intentos
                time.sleep(0.5)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en intento {attempt}: {e}")
                test_results['total_attempts'] = attempt
                break
        
        # Test de falsos positivos - intentar desde otra IP (simular con user-agent diferente)
        logger.info(" Verificando falsos positivos...")
        
        try:
            different_headers = {
                'User-Agent': 'SecurityTest-DifferentClient/1.0',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                login_url,
                json={'username': 'testuser1', 'password': 'test123'},
                headers=different_headers,
                timeout=self.request_timeout
            )
            
            if response.status_code == 429:
                test_results['false_positives'] += 1
                logger.warning(" Falso positivo detectado - usuario legítimo bloqueado")
            else:
                logger.info(" Sin falsos positivos - usuario legítimo puede acceder")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error verificando falsos positivos: {e}")
        
        # Calcular métricas
        if test_results['detection_times']:
            avg_detection_time = statistics.mean(test_results['detection_times'])
            test_results['avg_detection_time'] = avg_detection_time
            logger.info(f" Tiempo promedio de detección: {avg_detection_time:.3f}s")
        
        false_positive_rate = test_results['false_positives'] / max(1, test_results['total_attempts'])
        test_results['false_positive_rate'] = false_positive_rate
        
        logger.info(f" Tasa de falsos positivos: {false_positive_rate:.3%}")
        
        return test_results
    
    def test_jwt_validation_performance(self) -> Dict:
        """
        Test 2: Verificar rendimiento de validación JWT
        """
        logger.info(" Iniciando test de rendimiento de validación JWT...")
        
        test_results = {
            'jwt_obtained': False,
            'token': None,
            'validation_times': [],
            'avg_validation_time': 0,
            'successful_validations': 0,
            'failed_validations': 0
        }
        
        # Obtener JWT válido
        login_url = f"{self.auth_url}/login/"
        valid_credentials = {
            'username': 'testuser1',
            'password': 'test123'
        }
        
        try:
            logger.info("Obteniendo JWT válido...")
            response = requests.post(login_url, json=valid_credentials, timeout=self.request_timeout)
            if response.status_code != 200:
                logger.error("No se pudo obtener JWT para test")
                return test_results
            
            jwt_token = response.json().get('access')
            test_results['jwt_obtained'] = True
            test_results['token'] = jwt_token
            logger.info(" JWT obtenido exitosamente")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obteniendo JWT: {e}")
            return test_results
        
        # Test de validación múltiple
        validation_times = []
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        logger.info("Realizando múltiples validaciones JWT...")
        
        # Realizar 50 validaciones para obtener estadísticas confiables
        for i in range(50):
            start_time = time.time()
            
            try:
                response = requests.get(
                    f"{self.patients_url}/patients/",
                    headers=headers,
                    timeout=self.request_timeout
                )
                
                end_time = time.time()
                validation_time = (end_time - start_time) * 1000  # Convertir a ms
                validation_times.append(validation_time)
                
                if response.status_code == 200:
                    test_results['successful_validations'] += 1
                else:
                    test_results['failed_validations'] += 1
                    logger.error(f"Validación {i+1} falló: {response.text}")
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Completadas {i+1}/50 validaciones")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error en validación {i+1}: {e}")
                test_results['failed_validations'] += 1
        
        # Calcular estadísticas
        if validation_times:
            test_results['validation_times'] = validation_times
            test_results['avg_validation_time'] = statistics.mean(validation_times)
            test_results['min_validation_time'] = min(validation_times)
            test_results['max_validation_time'] = max(validation_times)
            test_results['p95_validation_time'] = sorted(validation_times)[int(0.95 * len(validation_times))]
            
            logger.info(f" Tiempo promedio de validación JWT: {test_results['avg_validation_time']:.2f}ms")
            logger.info(f" Tiempo mínimo: {test_results['min_validation_time']:.2f}ms")
            logger.info(f" Tiempo máximo: {test_results['max_validation_time']:.2f}ms")
            logger.info(f"Percentil 95: {test_results['p95_validation_time']:.2f}ms")
            
            # Verificar si cumple el ASR (< 250ms)
            if test_results['avg_validation_time'] < 250:
                logger.info(" ASR cumplido: Validación JWT < 250ms")
            else:
                logger.error(" ASR NO cumplido: Validación JWT > 250ms")
        
        return test_results
    
    def test_endpoint_protection(self) -> Dict:
        """
        Test 3: Verificar que todos los endpoints requieren autenticación
        """
        logger.info(" Iniciando test de protección de endpoints...")
        
        test_results = {
            'protected_endpoints': 0,
            'unprotected_endpoints': 0,
            'endpoint_tests': []
        }
        
        # Endpoints a testear
        endpoints_to_test = [
            f"{self.patients_url}/patients/",
            f"{self.patients_url}/patients/search/",
            f"{self.patients_url}/stats/",
        ]
        
        for endpoint in endpoints_to_test:
            logger.info(f"Testeando endpoint: {endpoint}")
            
            try:
                # Intentar acceso sin token
                response = requests.get(endpoint, timeout=self.request_timeout)
                
                endpoint_test = {
                    'endpoint': endpoint,
                    'status_code': response.status_code,
                    'protected': response.status_code in [401, 403]  # Unauthorized or Forbidden
                }
                
                if endpoint_test['protected']:
                    test_results['protected_endpoints'] += 1
                    logger.info(f" Endpoint protegido: {endpoint} (Status: {response.status_code})")
                else:
                    test_results['unprotected_endpoints'] += 1
                    logger.error(f" Endpoint NO protegido: {endpoint} (Status: {response.status_code})")
                
                test_results['endpoint_tests'].append(endpoint_test)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error testeando endpoint {endpoint}: {e}")
                test_results['endpoint_tests'].append({
                    'endpoint': endpoint,
                    'error': str(e),
                    'protected': False
                })
        
        logger.info(f" Endpoints protegidos: {test_results['protected_endpoints']}")
        logger.info(f" Endpoints desprotegidos: {test_results['unprotected_endpoints']}")
        
        return test_results
    
    def test_dos_prevention(self) -> Dict:
        """
        Test 4: Test básico de prevención DoS (múltiples requests simultáneos)
        """
        logger.info(" Iniciando test básico de prevención DoS...")
        
        test_results = {
            'total_requests': 0,
            'successful_requests': 0,
            'blocked_requests': 0,
            'avg_response_time': 0,
            'response_times': []
        }
        
        # Obtener JWT válido primero
        login_url = f"{self.auth_url}/login/"
        valid_credentials = {'username': 'testuser1', 'password': 'test123'}
        
        try:
            response = requests.post(login_url, json=valid_credentials, timeout=self.request_timeout)
            if response.status_code != 200:
                logger.error("No se pudo obtener JWT para test DoS")
                return test_results
            
            jwt_token = response.json().get('access')
            headers = {'Authorization': f'Bearer {jwt_token}'}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error obteniendo JWT para test DoS: {e}")
            return test_results
        
        # Realizar múltiples requests simultáneos
        def make_request(request_id):
            try:
                start_time = time.time()
                response = requests.get(
                    f"{self.patients_url}/patients/",
                    headers=headers,
                    timeout=self.request_timeout
                )
                end_time = time.time()
                
                return {
                    'id': request_id,
                    'status_code': response.status_code,
                    'response_time': end_time - start_time,
                    'success': response.status_code == 200
                }
            except Exception as e:
                return {
                    'id': request_id,
                    'error': str(e),
                    'success': False
                }
        
        logger.info("Realizando 20 requests simultáneos...")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request, i) for i in range(20)]
            
            for future in as_completed(futures):
                result = future.result()
                test_results['total_requests'] += 1
                
                if result.get('success'):
                    test_results['successful_requests'] += 1
                    test_results['response_times'].append(result['response_time'])
                elif result.get('status_code') == 429:
                    test_results['blocked_requests'] += 1
                    logger.info(f"Request {result['id']} bloqueado por rate limiting")
        
        # Calcular estadísticas
        if test_results['response_times']:
            test_results['avg_response_time'] = statistics.mean(test_results['response_times'])
            logger.info(f" Tiempo promedio de respuesta: {test_results['avg_response_time']:.3f}s")
        
        logger.info(f" Requests exitosos: {test_results['successful_requests']}/{test_results['total_requests']}")
        logger.info(f" Requests bloqueados: {test_results['blocked_requests']}")
        
        return test_results
    
    def run_all_tests(self) -> Dict:
        """
        Ejecutar todos los tests de seguridad
        """
        logger.info(" Iniciando experimento completo de seguridad...")
        
        start_time = datetime.now()
        
        # Ejecutar tests
        self.results['brute_force_test'] = self.test_brute_force_protection()
        time.sleep(2)  # Pausa entre tests
        
        self.results['jwt_validation_test'] = self.test_jwt_validation_performance()
        time.sleep(2)
        
        self.results['endpoint_protection_test'] = self.test_endpoint_protection()
        time.sleep(2)
        
        self.results['dos_prevention_test'] = self.test_dos_prevention()
        
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds()
        
        # Generar reporte final
        report = self.generate_security_report(total_duration)
        
        return report
    
    def generate_security_report(self, duration: float) -> Dict:
        """
        Generar reporte final del experimento de seguridad
        """
        logger.info(" Generando reporte final de seguridad...")
        
        report = {
            'experiment': 'Security Validation (ASR-2)',
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': duration,
            'server_ip': self.server_ip,
            'asr_compliance': {},
            'test_results': self.results,
            'summary': {}
        }
        
        # Evaluar cumplimiento de ASRs
        asr_compliance = {}
        
        # ASR 2.1: Tiempo de detección de fuerza bruta < 1 segundo
        brute_force = self.results.get('brute_force_test', {})
        if brute_force.get('avg_detection_time'):
            asr_compliance['brute_force_detection'] = {
                'requirement': '< 1 second',
                'actual': f"{brute_force['avg_detection_time']:.3f}s",
                'compliant': brute_force['avg_detection_time'] < 1.0
            }
        
        # ASR 2.2: Tasa de falsos positivos < 0.1%
        if 'false_positive_rate' in brute_force:
            asr_compliance['false_positive_rate'] = {
                'requirement': '< 0.1%',
                'actual': f"{brute_force['false_positive_rate']:.3%}",
                'compliant': brute_force['false_positive_rate'] < 0.001
            }
        
        # ASR 2.3: Tiempo de validación JWT < 250ms
        jwt_test = self.results.get('jwt_validation_test', {})
        if jwt_test.get('avg_validation_time'):
            asr_compliance['jwt_validation_time'] = {
                'requirement': '< 250ms',
                'actual': f"{jwt_test['avg_validation_time']:.2f}ms",
                'compliant': jwt_test['avg_validation_time'] < 250.0
            }
        
        report['asr_compliance'] = asr_compliance
        
        # Resumen general
        total_compliant = sum(1 for asr in asr_compliance.values() if asr.get('compliant', False))
        total_asrs = len(asr_compliance)
        
        report['summary'] = {
            'total_asrs_evaluated': total_asrs,
            'compliant_asrs': total_compliant,
            'compliance_percentage': (total_compliant / max(1, total_asrs)) * 100,
            'overall_security_status': 'PASS' if total_compliant == total_asrs else 'FAIL'
        }
        
        # Log del resumen
        logger.info("=" * 60)
        logger.info("🔐 REPORTE FINAL DE SEGURIDAD")
        logger.info("=" * 60)
        logger.info(f"Servidor testeado: {self.server_ip}")
        logger.info(f"Duración del experimento: {duration:.2f} segundos")
        logger.info(f"ASRs evaluados: {total_asrs}")
        logger.info(f"ASRs cumplidos: {total_compliant}")
        logger.info(f"Porcentaje de cumplimiento: {report['summary']['compliance_percentage']:.1f}%")
        logger.info(f"Estado general: {report['summary']['overall_security_status']}")
        
        for asr_name, asr_data in asr_compliance.items():
            status = "✅ PASS" if asr_data['compliant'] else "❌ FAIL"
            logger.info(f"{asr_name}: {asr_data['actual']} (req: {asr_data['requirement']}) {status}")
        
        logger.info("=" * 60)
        
        return report

def main():
    parser = argparse.ArgumentParser(description='Security Experiment - ASR-2 Validation')
    parser.add_argument('--server-ip', required=True, help='IP address of the server to test')
    parser.add_argument('--output', default='security_experiment_results.json', help='Output file for results')
    
    args = parser.parse_args()
    
    # Ejecutar experimento
    experiment = SecurityExperiment(args.server_ip)
    results = experiment.run_all_tests()
    
    # Guardar resultados
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    logger.info(f"📄 Resultados guardados en: {args.output}")
    
    # Mostrar resultado final
    if results['summary']['overall_security_status'] == 'PASS':
        logger.info("🎉 EXPERIMENTO DE SEGURIDAD: EXITOSO")
    else:
        logger.error("💥 EXPERIMENTO DE SEGURIDAD: FALLIDO")

if __name__ == "__main__":
    main()