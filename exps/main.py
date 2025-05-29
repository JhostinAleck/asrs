#!/usr/bin/env python3
"""
=============================================================================
INTERFAZ GRÁFICA PARA EXPERIMENTOS ASR
=============================================================================

Interfaz moderna para ejecutar experimentos de Latencia y Seguridad
con configuración avanzada y visualización de logs en tiempo real.

Requisitos:
- pip install customtkinter
- pip install pillow
- Scripts de experimentos en el mismo directorio
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import subprocess
import sys
import os
import json
import logging
from datetime import datetime
from typing import Dict, List
import queue
import time

# Configurar CustomTkinter
ctk.set_appearance_mode("dark")  # Modes: "System" (default), "Dark", "Light"
ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

class LogHandler(logging.Handler):
    """Handler personalizado para mostrar logs en la interfaz"""
    
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(msg)

class ASRExperimentGUI:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("🧪 ASR Experiments Dashboard")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)
        
        # Variables de configuración con valores por defecto
        self.config = {
            'server_ip': ctk.StringVar(value="35.202.107.19"),
            'username': ctk.StringVar(value="testuser1"),
            'password': ctk.StringVar(value="test123"),
            'output_dir': ctk.StringVar(value="./results"),
            'timeout': ctk.IntVar(value=10),
            'concurrent_users': ctk.StringVar(value="1,5,10,20"),
            'test_requests': ctk.IntVar(value=100),
            'warmup_requests': ctk.IntVar(value=10)
        }
        
        # Estado de la aplicación
        self.running_experiments = {}
        self.log_queue = queue.Queue()
        
        # Configurar logging
        self.setup_logging()
        
        # Crear interfaz
        self.setup_ui()
        
        # Iniciar monitor de logs
        self.root.after(100, self.process_log_queue)
        
        # Cargar configuración guardada
        self.load_config()
    
    def setup_logging(self):
        """Configurar sistema de logging"""
        # Crear formatter
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Handler para la interfaz
        self.gui_handler = LogHandler(self.log_queue)
        self.gui_handler.setFormatter(formatter)
        
        # Configurar logger root
        logging.getLogger().addHandler(self.gui_handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def setup_ui(self):
        """Crear la interfaz de usuario"""
        # Header
        self.create_header()
        
        # Main content con pestañas
        self.create_main_content()
        
        # Footer con controles
        self.create_footer()
    
    def create_header(self):
        """Crear header de la aplicación"""
        header_frame = ctk.CTkFrame(self.root, height=80, corner_radius=0)
        header_frame.pack(fill="x", padx=0, pady=(0, 10))
        header_frame.pack_propagate(False)
        
        # Título principal
        title_label = ctk.CTkLabel(
            header_frame,
            text="🧪 ASR Experiments Dashboard",
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack(side="left", padx=30, pady=20)
        
        # Indicador de estado
        self.status_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        self.status_frame.pack(side="right", padx=30, pady=20)
        
        self.status_label = ctk.CTkLabel(
            self.status_frame,
            text="🟢 Listo",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#4ade80"
        )
        self.status_label.pack()
        
        # Hora actual
        self.time_label = ctk.CTkLabel(
            self.status_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        self.time_label.pack()
        self.update_time()
    
    def create_main_content(self):
        """Crear contenido principal con pestañas"""
        # Frame principal
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=20)
        
        # Crear notebook para pestañas
        self.notebook = ctk.CTkTabview(main_frame)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Pestañas
        self.create_config_tab()
        self.create_latency_tab()
        self.create_security_tab()
        self.create_logs_tab()
        self.create_results_tab()
    
    def create_config_tab(self):
        """Crear pestaña de configuración"""
        config_tab = self.notebook.add("⚙️ Configuración")
        
        # Crear scrollable frame
        scrollable_frame = ctk.CTkScrollableFrame(config_tab)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Sección: Servidor
        server_frame = ctk.CTkFrame(scrollable_frame)
        server_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            server_frame,
            text="🌐 Configuración del Servidor",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))
        
        # IP del servidor
        ip_frame = ctk.CTkFrame(server_frame, fg_color="transparent")
        ip_frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(ip_frame, text="IP del Servidor:", width=120).pack(side="left", pady=5)
        ip_entry = ctk.CTkEntry(
            ip_frame,
            textvariable=self.config['server_ip'],
            placeholder_text="ej., 35.202.107.19",
            width=300
        )
        ip_entry.pack(side="left", padx=(10, 0), pady=5)
        
        # Botón test conexión
        test_btn = ctk.CTkButton(
            ip_frame,
            text="🔍 Probar Conexión",
            command=self.test_connection,
            width=120
        )
        test_btn.pack(side="right", padx=(10, 0), pady=5)
        
        # Sección: Credenciales
        creds_frame = ctk.CTkFrame(scrollable_frame)
        creds_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            creds_frame,
            text="🔑 Authentication",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))
        
        # Username
        user_frame = ctk.CTkFrame(creds_frame, fg_color="transparent")
        user_frame.pack(fill="x", padx=20)
        
        ctk.CTkLabel(user_frame, text="Usuario:", width=120).pack(side="left", pady=5)
        ctk.CTkEntry(
            user_frame,
            textvariable=self.config['username'],
            width=200
        ).pack(side="left", padx=(10, 0), pady=5)
        
        # Password
        pass_frame = ctk.CTkFrame(creds_frame, fg_color="transparent")
        pass_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkLabel(pass_frame, text="Contraseña:", width=120).pack(side="left", pady=5)
        ctk.CTkEntry(
            pass_frame,
            textvariable=self.config['password'],
            show="*",
            width=200
        ).pack(side="left", padx=(10, 0), pady=5)
        
        # Sección: Test Parameters
        params_frame = ctk.CTkFrame(scrollable_frame)
        params_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            params_frame,
            text="🎯 Parámetros de Prueba",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))
        
        # Grid para parámetros
        params_grid = ctk.CTkFrame(params_frame, fg_color="transparent")
        params_grid.pack(fill="x", padx=20, pady=(0, 20))
        
        # Fila 1
        row1 = ctk.CTkFrame(params_grid, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row1, text="Solicitudes de Prueba:", width=120).pack(side="left")
        ctk.CTkEntry(row1, textvariable=self.config['test_requests'], width=100).pack(side="left", padx=10)
        
        ctk.CTkLabel(row1, text="Solicitudes de Calentamiento:", width=130).pack(side="left", padx=(30, 0))
        ctk.CTkEntry(row1, textvariable=self.config['warmup_requests'], width=100).pack(side="left", padx=10)
        
        # Fila 2
        row2 = ctk.CTkFrame(params_grid, fg_color="transparent")
        row2.pack(fill="x", pady=5)
        
        ctk.CTkLabel(row2, text="Tiempo de Espera (s):", width=120).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.config['timeout'], width=100).pack(side="left", padx=10)
        
        ctk.CTkLabel(row2, text="Usuarios Concurrentes:", width=130).pack(side="left", padx=(30, 0))
        ctk.CTkEntry(row2, textvariable=self.config['concurrent_users'], width=150).pack(side="left", padx=10)
        
        # Sección: Output
        output_frame = ctk.CTkFrame(scrollable_frame)
        output_frame.pack(fill="x")
        
        ctk.CTkLabel(
            output_frame,
            text="📁 Configuración de Salida",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(20, 10))
        
        dir_frame = ctk.CTkFrame(output_frame, fg_color="transparent")
        dir_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkLabel(dir_frame, text="Directorio de Salida:", width=120).pack(side="left", pady=5)
        ctk.CTkEntry(
            dir_frame,
            textvariable=self.config['output_dir'],
            width=300
        ).pack(side="left", padx=(10, 0), pady=5)
        
        ctk.CTkButton(
            dir_frame,
            text="📂 Examinar",
            command=self.browse_output_dir,
            width=80
        ).pack(side="left", padx=(10, 0), pady=5)
        
        # Botones de configuración
        config_buttons = ctk.CTkFrame(output_frame, fg_color="transparent")
        config_buttons.pack(fill="x", padx=20, pady=(10, 20))
        
        ctk.CTkButton(
            config_buttons,
            text="💾 Guardar Config.",
            command=self.save_config,
            width=120
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            config_buttons,
            text="📁 Cargar Config.",
            command=self.load_config_file,
            width=120
        ).pack(side="left", padx=(0, 10))
        
        ctk.CTkButton(
            config_buttons,
            text="🔄 Restablecer Predeterminados",
            command=self.reset_config,
            width=150
        ).pack(side="left", padx=(0, 10))
    
    def create_latency_tab(self):
        """Crear pestaña de experimento de latencia"""
        latency_tab = self.notebook.add("⚡ Prueba de Latencia")
        
        # Frame principal
        main_frame = ctk.CTkFrame(latency_tab)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header de la pestaña
        header = ctk.CTkFrame(main_frame)
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header,
            text="⚡ Experimento de Latencia (ASR-3)",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left", padx=20, pady=20)
        
        # Estado del experimento
        self.latency_status = ctk.CTkLabel(
            header,
            text="🔴 No Ejecutando",
            font=ctk.CTkFont(size=16),
            text_color="#ef4444"
        )
        self.latency_status.pack(side="right", padx=20, pady=20)
        
        # Descripción
        desc_frame = ctk.CTkFrame(main_frame)
        desc_frame.pack(fill="x", pady=(0, 20))
        
        desc_text = """
🎯 Objetivo: Verificar que las consultas de pacientes a través del flujo completo (Nginx → User Manager → Patient Manager → PostgreSQL) 
    se completen en menos de 500ms para el percentil 95, incluyendo la validación JWT y la consulta a la BD.

📊 Métricas a evaluar:
    • Latencia extremo a extremo P95: < 500ms
    • Latencia de validación JWT: < 50ms  
    • Latencia de consulta BD: < 200ms
        """
        
        ctk.CTkLabel(
            desc_frame,
            text=desc_text,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left"
        ).pack(fill="x", padx=20, pady=15)
        
        # Pruebas disponibles
        tests_frame = ctk.CTkFrame(main_frame)
        tests_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            tests_frame,
            text="🔧 Pruebas Disponibles",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        # Checkboxes para pruebas
        self.latency_tests = {
            'authentication': ctk.BooleanVar(value=True),
            'patient_list': ctk.BooleanVar(value=True),
            'patient_detail': ctk.BooleanVar(value=True),
            'patient_search': ctk.BooleanVar(value=True),
            'end_to_end': ctk.BooleanVar(value=True),
            'concurrent_load': ctk.BooleanVar(value=True)
        }
        
        tests_grid = ctk.CTkFrame(tests_frame, fg_color="transparent")
        tests_grid.pack(fill="x", padx=20, pady=(0, 15))
        
        test_labels = {
            'authentication': '🔑 Latencia de Autenticación',
            'patient_list': '📋 Latencia de Lista de Pacientes',
            'patient_detail': '👤 Latencia de Detalle de Paciente',
            'patient_search': '🔍 Latencia de Búsqueda de Pacientes',
            'end_to_end': '🔄 Latencia Extremo a Extremo',
            'concurrent_load': '👥 Prueba de Carga Concurrente'
        }
        
        # Crear checkboxes en 2 columnas
        for i, (key, var) in enumerate(self.latency_tests.items()):
            row = i // 2
            col = i % 2
            
            if col == 0:
                row_frame = ctk.CTkFrame(tests_grid, fg_color="transparent")
                row_frame.pack(fill="x", pady=2)
            
            checkbox = ctk.CTkCheckBox(
                row_frame,
                text=test_labels[key],
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            checkbox.pack(side="left" if col == 0 else "right", padx=20)
        
        # Controles
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.pack(fill="x")
        
        ctk.CTkButton(
            controls_frame,
            text="▶️ Iniciar Prueba de Latencia",
            command=self.start_latency_experiment,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=20, pady=20)
        
        ctk.CTkButton(
            controls_frame,
            text="⏹️ Detener Prueba",
            command=lambda: self.stop_experiment('latency'),
            width=120,
            height=40,
            fg_color="#ef4444",
            hover_color="#dc2626"
        ).pack(side="left", padx=10, pady=20)
        
        # Progress bar
        self.latency_progress = ctk.CTkProgressBar(controls_frame)
        self.latency_progress.pack(side="right", fill="x", expand=True, padx=(50, 20), pady=20)
        self.latency_progress.set(0)
    
    def create_security_tab(self):
        """Crear pestaña de experimento de seguridad"""
        security_tab = self.notebook.add("🔐 Prueba de Seguridad")
        
        # Frame principal
        main_frame = ctk.CTkFrame(security_tab)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header de la pestaña
        header = ctk.CTkFrame(main_frame)
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header,
            text="🔐 Experimento de Seguridad (ASR-2)",
            font=ctk.CTkFont(size=24, weight="bold")
        ).pack(side="left", padx=20, pady=20)
        
        # Estado del experimento
        self.security_status = ctk.CTkLabel(
            header,
            text="🔴 No Ejecutando",
            font=ctk.CTkFont(size=16),
            text_color="#ef4444"
        )
        self.security_status.pack(side="right", padx=20, pady=20)
        
        # Descripción
        desc_frame = ctk.CTkFrame(main_frame)
        desc_frame.pack(fill="x", pady=(0, 20))
        
        desc_text = """
🎯 Objetivo: Verificar que el sistema previene ataques de fuerza bruta bloqueando automáticamente IPs después de 5 intentos 
    fallidos en 5 minutos, y que todos los endpoints requieren autenticación JWT válida.

📊 Métricas a evaluar:
    • Tiempo de detección de ataque de fuerza bruta: < 1 segundo
    • Tasa de falsos positivos en bloqueo de IP: < 0.1%
    • Tiempo de validación JWT: < 250ms
        """
        
        ctk.CTkLabel(
            desc_frame,
            text=desc_text,
            font=ctk.CTkFont(size=12),
            anchor="w",
            justify="left"
        ).pack(fill="x", padx=20, pady=15)
        
        # Pruebas disponibles
        tests_frame = ctk.CTkFrame(main_frame)
        tests_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            tests_frame,
            text="🔧 Pruebas Disponibles",
            font=ctk.CTkFont(size=18, weight="bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        # Checkboxes para pruebas de seguridad
        self.security_tests = {
            'brute_force': ctk.BooleanVar(value=True),
            'jwt_validation': ctk.BooleanVar(value=True),
            'endpoint_protection': ctk.BooleanVar(value=True),
            'dos_prevention': ctk.BooleanVar(value=True)
        }
        
        security_tests_grid = ctk.CTkFrame(tests_frame, fg_color="transparent")
        security_tests_grid.pack(fill="x", padx=20, pady=(0, 15))
        
        security_test_labels = {
            'brute_force': '🛡️ Protección Fuerza Bruta',
            'jwt_validation': '🔑 Rendimiento Validación JWT',
            'endpoint_protection': '🚪 Protección de Endpoints',
            'dos_prevention': '⚡ Prevención DoS'
        }
        
        for key, var in self.security_tests.items():
            checkbox = ctk.CTkCheckBox(
                security_tests_grid,
                text=security_test_labels[key],
                variable=var,
                font=ctk.CTkFont(size=12)
            )
            checkbox.pack(anchor="w", padx=20, pady=5)
        
        # Advertencia de seguridad
        warning_frame = ctk.CTkFrame(main_frame, fg_color="#451a03", border_color="#f59e0b", border_width=2)
        warning_frame.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            warning_frame,
            text="⚠️ Advertencia de Seguridad",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#f59e0b"
        ).pack(anchor="w", padx=20, pady=(15, 5))
        
        ctk.CTkLabel(
            warning_frame,
            text="Esta prueba intentará ataques de fuerza bruta y podría bloquear temporalmente tu IP.\nAsegúrate de tener la autorización adecuada antes de ejecutar pruebas de seguridad.",
            font=ctk.CTkFont(size=12),
            text_color="#fbbf24",
            anchor="w",
            justify="left"
        ).pack(fill="x", padx=20, pady=(0, 15))
        
        # Controles
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.pack(fill="x")
        
        ctk.CTkButton(
            controls_frame,
            text="🔐 Iniciar Prueba de Seguridad",
            command=self.start_security_experiment,
            width=200,
            height=40,
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left", padx=20, pady=20)
        
        ctk.CTkButton(
            controls_frame,
            text="⏹️ Detener Prueba",
            command=lambda: self.stop_experiment('security'),
            width=120,
            height=40,
            fg_color="#ef4444",
            hover_color="#dc2626"
        ).pack(side="left", padx=10, pady=20)
        
        # Progress bar
        self.security_progress = ctk.CTkProgressBar(controls_frame)
        self.security_progress.pack(side="right", fill="x", expand=True, padx=(50, 20), pady=20)
        self.security_progress.set(0)
    
    def create_logs_tab(self):
        """Crear pestaña de logs"""
        logs_tab = self.notebook.add("📝 Registros")
        
        # Frame principal
        main_frame = ctk.CTkFrame(logs_tab)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header con controles
        header = ctk.CTkFrame(main_frame)
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header,
            text="📝 Registros en Tiempo Real",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=20, pady=15)
        
        # Controles de logs
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", padx=20, pady=15)
        
        ctk.CTkButton(
            controls,
            text="🗑️ Limpiar Registros",
            command=self.clear_logs,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            controls,
            text="💾 Guardar Registros",
            command=self.save_logs,
            width=100
        ).pack(side="left", padx=5)
        
        # Filtros de log level
        filter_frame = ctk.CTkFrame(main_frame)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(filter_frame, text="Nivel de Registro:").pack(side="left", padx=20, pady=10)
        
        self.log_level = ctk.StringVar(value="ALL")
        levels = ["ALL", "INFO", "ADVERTENCIA", "ERROR"]
        
        for level in levels:
            ctk.CTkRadioButton(
                filter_frame,
                text=level,
                variable=self.log_level,
                value=level,
                command=self.filter_logs
            ).pack(side="left", padx=10, pady=10)
        
        # Área de logs
        logs_frame = ctk.CTkFrame(main_frame)
        logs_frame.pack(fill="both", expand=True)
        
        # Text widget con scrollbar
        self.logs_text = ctk.CTkTextbox(
            logs_frame,
            font=ctk.CTkFont(family="Consolas", size=10),
            wrap="word"
        )
        self.logs_text.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Log inicial
        self.add_log("🚀 GUI de Experimentos ASR inicializada")
        self.add_log(f"📅 Iniciado a las: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def create_results_tab(self):
        """Crear pestaña de resultados"""
        results_tab = self.notebook.add("📊 Resultados")
        
        # Frame principal
        main_frame = ctk.CTkFrame(results_tab)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        header = ctk.CTkFrame(main_frame)
        header.pack(fill="x", pady=(0, 20))
        
        ctk.CTkLabel(
            header,
            text="📊 Resultados de Experimentos",
            font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=20, pady=15)
        
        # Controles de resultados
        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="right", padx=20, pady=15)
        
        ctk.CTkButton(
            controls,
            text="🔄 Actualizar",
            command=self.refresh_results,
            width=100
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            controls,
            text="📁 Abrir Carpeta de Resultados",
            command=self.open_results_folder,
            width=150
        ).pack(side="left", padx=5)
        
        # Lista de resultados
        self.results_frame = ctk.CTkScrollableFrame(main_frame)
        self.results_frame.pack(fill="both", expand=True)
        
        # Cargar resultados existentes
        self.refresh_results()
    
    def create_footer(self):
        """Crear footer con información del sistema"""
        footer_frame = ctk.CTkFrame(self.root, height=50, corner_radius=0)
        footer_frame.pack(fill="x", side="bottom")
        footer_frame.pack_propagate(False)
        
        # Info del sistema
        system_info = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} | CustomTkinter"
        
        ctk.CTkLabel(
            footer_frame,
            text=system_info,
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(side="left", padx=20, pady=15)
        
        # Versión de la aplicación
        ctk.CTkLabel(
            footer_frame,
            text="GUI Experimentos ASR v1.0",
            font=ctk.CTkFont(size=10),
            text_color="#64748b"
        ).pack(side="right", padx=20, pady=15)
    
    # ===================== MÉTODOS DE FUNCIONALIDAD =====================
    
    def update_time(self):
        """Actualizar hora en el header"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.time_label.configure(text=current_time)
        self.root.after(1000, self.update_time)
    
    def update_status(self, status, color="#4ade80"):
        """Actualizar estado general"""
        self.status_label.configure(text=status, text_color=color)
    
    def test_connection(self):
        """Probar conexión con el servidor"""
        server_ip = self.config['server_ip'].get()
        if not server_ip:
            messagebox.showerror("Error", "Por favor, ingresa una dirección IP del servidor")
            return
        
        self.add_log(f"🔍 Probando conexión con {server_ip}...")
        
        def test_thread():
            try:
                import requests
                response = requests.get(f"http://{server_ip}/health", timeout=5)
                if response.status_code == 200:
                    self.add_log(f"✅ Conexión exitosa con {server_ip}")
                    self.root.after(0, lambda: messagebox.showinfo("Éxito", f"¡Conexión con {server_ip} exitosa!"))
                else:
                    self.add_log(f"⚠️ El servidor respondió con estado {response.status_code}")
                    self.root.after(0, lambda: messagebox.showwarning("Warning", f"Server responded with status {response.status_code}"))
            except Exception as e:
                self.add_log(f"❌ Falló la conexión: {str(e)}")
                self.root.after(0, lambda: messagebox.showerror("Falló la Conexión", f"No se pudo conectar a {server_ip}:\n{str(e)}"))
        
        threading.Thread(target=test_thread, daemon=True).start()
    
    def browse_output_dir(self):
        """Seleccionar directorio de salida"""
        directory = filedialog.askdirectory(initialdir=self.config['output_dir'].get())
        if directory:
            self.config['output_dir'].set(directory)
    
    def save_config(self):
        """Guardar configuración actual"""
        config_data = {key: var.get() for key, var in self.config.items()}
        
        try:
            os.makedirs("config", exist_ok=True)
            with open("config/asr_gui_config.json", "w") as f:
                json.dump(config_data, f, indent=2)
            
            self.add_log("💾 Configuración guardada exitosamente")
            messagebox.showinfo("Éxito", "¡Configuración guardada exitosamente!")
        except Exception as e:
            self.add_log(f"❌ Error saving configuration: {str(e)}")
            messagebox.showerror("Error", f"No se pudo guardar la configuración:\n{str(e)}")
    
    def load_config(self):
        """Cargar configuración guardada"""
        try:
            if os.path.exists("config/asr_gui_config.json"):
                with open("config/asr_gui_config.json", "r") as f:
                    config_data = json.load(f)
                
                for key, value in config_data.items():
                    if key in self.config:
                        self.config[key].set(value)
                
                self.add_log("📁 Configuración cargada exitosamente")
        except Exception as e:
            self.add_log(f"⚠️ No se pudo cargar la configuración guardada: {str(e)}")
    
    def load_config_file(self):
        """Cargar configuración desde archivo"""
        file_path = filedialog.askopenfilename(
            title="Cargar Configuración",
            filetypes=[("Archivos JSON", "*.json"), ("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            initialfilename=f"asr_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        if file_path:
            try:
                with open(file_path, "r") as f:
                    config_data = json.load(f)
                
                for key, value in config_data.items():
                    if key in self.config:
                        self.config[key].set(value)
                
                self.add_log(f"📁 Configuración cargada desde {file_path}")
                messagebox.showinfo("Éxito", "¡Configuración cargada exitosamente!")
            except Exception as e:
                self.add_log(f"❌ Error loading configuration: {str(e)}")
                messagebox.showerror("Error", f"No se pudo cargar la configuración:\n{str(e)}")
    
    def reset_config(self):
        """Resetear configuración a valores por defecto"""
        defaults = {
            'server_ip': "35.202.107.19",
            'username': "testuser1",
            'password': "test123",
            'output_dir': "./results",
            'timeout': 10,
            'concurrent_users': "1,5,10,20",
            'test_requests': 100,
            'warmup_requests': 10
        }
        
        for key, value in defaults.items():
            if key in self.config:
                self.config[key].set(value)
        
        self.add_log("🔄 Configuración restablecida a predeterminados")
        messagebox.showinfo("Éxito", "¡Configuración restablecida a valores predeterminados!")
    
    def start_latency_experiment(self):
        """Iniciar experimento de latencia"""
        if 'latency' in self.running_experiments:
            messagebox.showwarning("Warning", "¡El experimento de latencia ya está en ejecución!")
            return
        
        # Verificar que al menos un test esté seleccionado
        selected_tests = [name for name, var in self.latency_tests.items() if var.get()]
        if not selected_tests:
            messagebox.showerror("Error", "¡Por favor, selecciona al menos una prueba para ejecutar!")
            return
        
        self.add_log("⚡ Iniciando Experimento de Latencia...")
        self.latency_status.configure(text="🟡 Ejecutando", text_color="#f59e0b")
        self.update_status("🟡 Ejecutando Latency Test", "#f59e0b")
        
        # Crear argumentos para el script
        args = [
            sys.executable, "exps/latencia.py",
            "--server-ip", self.config['server_ip'].get(),
            "--output", os.path.join(self.config['output_dir'].get(), f"latencia_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        ]
        
        def run_experiment():
            try:
                # Crear directorio de salida si no existe
                os.makedirs(self.config['output_dir'].get(), exist_ok=True)
                
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                self.running_experiments['latency'] = process
                
                # Leer output en tiempo real
                for line in iter(process.stdout.readline, ''):
                    if line.strip():
                        self.add_log(f"⚡ {line.strip()}")
                    
                    # Actualizar progress bar (simulado)
                    progress = min(0.8, len(self.logs_text.get("1.0", "end").split('\n')) / 100)
                    self.root.after(0, lambda p=progress: self.latency_progress.set(p))
                
                process.wait()
                
                if process.returncode == 0:
                    self.add_log("✅ ¡Experimento de latencia completado exitosamente!")
                    self.root.after(0, lambda: self.latency_status.configure(text="✅ Completado", text_color="#4ade80"))
                    self.root.after(0, lambda: self.latency_progress.set(1.0))
                else:
                    self.add_log("❌ ¡Falló el experimento de latencia!")
                    self.root.after(0, lambda: self.latency_status.configure(text="❌ Fallido", text_color="#ef4444"))
                
            except Exception as e:
                self.add_log(f"❌ Error running latency experiment: {str(e)}")
                self.root.after(0, lambda: self.latency_status.configure(text="❌ Error", text_color="#ef4444"))
            finally:
                if 'latency' in self.running_experiments:
                    del self.running_experiments['latency']
                self.root.after(0, lambda: self.update_status("🟢 Listo"))
                self.root.after(0, self.refresh_results)
        
        threading.Thread(target=run_experiment, daemon=True).start()
    
    def start_security_experiment(self):
        """Iniciar experimento de seguridad"""
        if 'security' in self.running_experiments:
            messagebox.showwarning("Warning", "¡El experimento de seguridad ya está en ejecución!")
            return
        
        # Confirmar que el usuario entiende los riesgos
        result = messagebox.askyesno(
            "Advertencia de Prueba de Seguridad",
            "Esta prueba intentará ataques de fuerza bruta y podría bloquear temporalmente tu IP.\n\n¿Estás seguro de que quieres continuar?"
        )
        
        if not result:
            return
        
        # Verificar que al menos un test esté seleccionado
        selected_tests = [name for name, var in self.security_tests.items() if var.get()]
        if not selected_tests:
            messagebox.showerror("Error", "¡Por favor, selecciona al menos una prueba para ejecutar!")
            return
        
        self.add_log("🔐 Iniciando Experimento de Seguridad...")
        self.security_status.configure(text="🟡 Ejecutando", text_color="#f59e0b")
        self.update_status("🟡 Ejecutando Security Test", "#f59e0b")
        
        # Crear argumentos para el script
        args = [
            sys.executable, "exps/seguridad.py",
            "--server-ip", self.config['server_ip'].get(),
            "--output", os.path.join(self.config['output_dir'].get(), f"security_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        ]
        
        def run_experiment():
            try:
                # Crear directorio de salida si no existe
                os.makedirs(self.config['output_dir'].get(), exist_ok=True)
                
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                    bufsize=1
                )
                
                self.running_experiments['security'] = process
                
                # Leer output en tiempo real
                for line in iter(process.stdout.readline, ''):
                    if line.strip():
                        self.add_log(f"🔐 {line.strip()}")
                    
                    # Actualizar progress bar (simulado)
                    progress = min(0.8, len(self.logs_text.get("1.0", "end").split('\n')) / 50)
                    self.root.after(0, lambda p=progress: self.security_progress.set(p))
                
                process.wait()
                
                if process.returncode == 0:
                    self.add_log("✅ ¡Experimento de seguridad completado exitosamente!")
                    self.root.after(0, lambda: self.security_status.configure(text="✅ Completado", text_color="#4ade80"))
                    self.root.after(0, lambda: self.security_progress.set(1.0))
                else:
                    self.add_log("❌ ¡Falló el experimento de seguridad!")
                    self.root.after(0, lambda: self.security_status.configure(text="❌ Fallido", text_color="#ef4444"))
                
            except Exception as e:
                self.add_log(f"❌ Error running security experiment: {str(e)}")
                self.root.after(0, lambda: self.security_status.configure(text="❌ Error", text_color="#ef4444"))
            finally:
                if 'security' in self.running_experiments:
                    del self.running_experiments['security']
                self.root.after(0, lambda: self.update_status("🟢 Listo"))
                self.root.after(0, self.refresh_results)
        
        threading.Thread(target=run_experiment, daemon=True).start()
    
    def stop_experiment(self, experiment_type):
        """Detener experimento en ejecución"""
        if experiment_type in self.running_experiments:
            process = self.running_experiments[experiment_type]
            process.terminate()
            del self.running_experiments[experiment_type]
            
            self.add_log(f"⏹️ {experiment_type.title()} experimento detenido por el usuario")
            
            if experiment_type == 'latency':
                self.latency_status.configure(text="⏹️ Detenido", text_color="#64748b")
                self.latency_progress.set(0)
            else:
                self.security_status.configure(text="⏹️ Detenido", text_color="#64748b")
                self.security_progress.set(0)
            
            self.update_status("🟢 Listo")
        else:
            messagebox.showinfo("Info", f"Ningún experimento de {experiment_type} está en ejecución actualmente.")
    
    def add_log(self, message):
        """Añadir mensaje a los logs"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.logs_text.insert("end", formatted_message)
        self.logs_text.see("end")  # Auto-scroll to bottom
    
    def clear_logs(self):
        """Limpiar área de logs"""
        self.logs_text.delete("1.0", "end")
        self.add_log("🗑️ Registros limpiados")
    
    def save_logs(self):
        """Guardar logs a archivo"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Archivos de registro", "*.log"), ("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            initialfilename=f"asr_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.logs_text.get("1.0", "end"))
                
                self.add_log(f"💾 Registros guardados en {file_path}")
                messagebox.showinfo("Éxito", f"Logs saved to {file_path}")
            except Exception as e:
                self.add_log(f"❌ Error saving logs: {str(e)}")
                messagebox.showerror("Error", f"No se pudieron guardar los registros:\n{str(e)}")
    
    def filter_logs(self):
        """Filtrar logs por nivel (funcionalidad básica)"""
        # Esta es una implementación básica - en una versión completa
        # filtrarías el contenido basado en el nivel seleccionado
        level = self.log_level.get()
        self.add_log(f"🔍 Filtro de registro establecido a: {level}")
    
    def refresh_results(self):
        """Refrescar lista de resultados"""
        # Limpiar frame de resultados
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        
        output_dir = self.config['output_dir'].get()
        
        if not os.path.exists(output_dir):
            ctk.CTkLabel(
                self.results_frame,
                text="📁 No se encontró el directorio de resultados. Ejecuta un experimento primero.",
                font=ctk.CTkFont(size=14),
                text_color="#64748b"
            ).pack(pady=50)
            return
        
        # Buscar archivos de resultados
        result_files = []
        for file in os.listdir(output_dir):
            if file.endswith('.json') and ('latency_results' in file or 'security_results' in file):
                result_files.append(file)
        
        if not result_files:
            ctk.CTkLabel(
                self.results_frame,
                text="📊 No se encontraron archivos de resultados. Ejecuta un experimento primero.",
                font=ctk.CTkFont(size=14),
                text_color="#64748b"
            ).pack(pady=50)
            return
        
        # Mostrar archivos de resultados
        result_files.sort(reverse=True)  # Más recientes primero
        
        for file in result_files:
            file_path = os.path.join(output_dir, file)
            
            # Frame para cada resultado
            result_frame = ctk.CTkFrame(self.results_frame)
            result_frame.pack(fill="x", padx=10, pady=5)
            
            # Información del archivo
            info_frame = ctk.CTkFrame(result_frame, fg_color="transparent")
            info_frame.pack(fill="x", padx=15, pady=10)
            
            # Icono y nombre
            icon = "⚡" if "latency" in file else "🔐"
            file_label = ctk.CTkLabel(
                info_frame,
                text=f"{icon} {file}",
                font=ctk.CTkFont(size=14, weight="bold")
            )
            file_label.pack(side="left")
            
            # Fecha de modificación
            mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            time_label = ctk.CTkLabel(
                info_frame,
                text=f"📅 {mod_time.strftime('%Y-%m-%d %H:%M:%S')}",
                font=ctk.CTkFont(size=10),
                text_color="#64748b"
            )
            time_label.pack(side="left", padx=(20, 0))
            
            # Botones
            buttons_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            buttons_frame.pack(side="right")
            
            ctk.CTkButton(
                buttons_frame,
                text="👁️ Ver",
                command=lambda f=file_path: self.view_result_file(f),
                width=80
            ).pack(side="left", padx=2)
            
            ctk.CTkButton(
                buttons_frame,
                text="📊 Resumen",
                command=lambda f=file_path: self.show_result_summary(f),
                width=80
            ).pack(side="left", padx=2)
    
    def view_result_file(self, file_path):
        """Ver archivo de resultados completo"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Crear ventana para mostrar resultados
            result_window = ctk.CTkToplevel(self.root)
            result_window.title(f"Resultados: {os.path.basename(file_path)}")
            result_window.geometry("800x600")
            
            # Text widget con scroll
            text_widget = ctk.CTkTextbox(result_window, font=ctk.CTkFont(family="Consolas", size=10))
            text_widget.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Formatear JSON para mejor legibilidad
            try:
                json_data = json.loads(content)
                formatted_content = json.dumps(json_data, indent=2, ensure_ascii=False)
                text_widget.insert("1.0", formatted_content)
            except:
                text_widget.insert("1.0", content)
            
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo de resultados:\n{str(e)}")
    
    def show_result_summary(self, file_path):
        """Mostrar resumen de resultados"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Crear ventana de resumen
            summary_window = ctk.CTkToplevel(self.root)
            summary_window.title(f"Resumen: {os.path.basename(file_path)}")
            summary_window.geometry("600x400")
            
            # Frame con scroll
            scrollable_frame = ctk.CTkScrollableFrame(summary_window)
            scrollable_frame.pack(fill="both", expand=True, padx=20, pady=20)
            
            # Título
            ctk.CTkLabel(
                scrollable_frame,
                text=data.get('experiment', 'Experiment Results'),
                font=ctk.CTkFont(size=20, weight="bold")
            ).pack(pady=(0, 20))
            
            # Información general
            info_frame = ctk.CTkFrame(scrollable_frame)
            info_frame.pack(fill="x", pady=(0, 10))
            
            ctk.CTkLabel(info_frame, text="📊 Información General", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
            
            general_info = [
                ("🏠 Servidor", data.get('server_ip', 'N/D')),
                ("📅 Fecha y Hora", data.get('timestamp', 'N/D')),
                ("⏱️ Duración", f"{data.get('duration_seconds', 0):.2f} segundos"),
            ]
            
            for label, value in general_info:
                info_row = ctk.CTkFrame(info_frame, fg_color="transparent")
                info_row.pack(fill="x", padx=15, pady=2)
                ctk.CTkLabel(info_row, text=f"{label}: {value}", anchor="w").pack(fill="x")
            
            # Resumen de cumplimiento ASR
            if 'summary' in data:
                summary_frame = ctk.CTkFrame(scrollable_frame)
                summary_frame.pack(fill="x", pady=10)
                
                ctk.CTkLabel(summary_frame, text="✅ Cumplimiento ASR", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=15, pady=(15, 10))
                
                summary = data['summary']
                compliance_info = [
                    ("📋 ASRs Totales", summary.get('total_asrs_evaluated', 0)),
                    ("✅ ASRs Cumplidos", summary.get('compliant_asrs', 0)),
                    ("📊 % Cumplimiento", f"{summary.get('compliance_percentage', 0):.1f}%"),
                    ("🎯 Estado", summary.get('overall_performance_status', summary.get('overall_security_status', 'N/D')))
                ]
                
                for label, value in compliance_info:
                    info_row = ctk.CTkFrame(summary_frame, fg_color="transparent")
                    info_row.pack(fill="x", padx=15, pady=2)
                    ctk.CTkLabel(info_row, text=f"{label}: {value}", anchor="w").pack(fill="x")
                    
                ctk.CTkFrame(summary_frame, height=15, fg_color="transparent").pack()
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load result summary:\n{str(e)}")
    
    def open_results_folder(self):
        """Abrir carpeta de resultados"""
        output_dir = self.config['output_dir'].get()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        # Abrir carpeta según el OS
        import platform
        system = platform.system()
        
        try:
            if system == "Windows":
                os.startfile(output_dir)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", output_dir])
            else:  # Linux
                subprocess.run(["xdg-open", output_dir])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open results folder:\n{str(e)}")
    
    def process_log_queue(self):
        """Procesar cola de logs"""
        try:
            while True:
                message = self.log_queue.get_nowait()
                # Procesar mensaje si es necesario
        except queue.Empty:
            pass
        
        # Programar siguiente procesamiento
        self.root.after(100, self.process_log_queue)
    
    def run(self):
        """Ejecutar la aplicación"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.add_log("⏹️ Application interrupted by user")
        except Exception as e:
            self.add_log(f"❌ Application error: {str(e)}")
            messagebox.showerror("Application Error", f"An error occurred:\n{str(e)}")

def main():
    """Función principal"""
    try:
        app = ASRExperimentGUI()
        app.run()
    except ImportError as e:
        if "customtkinter" in str(e):
            messagebox.showerror(
                "Missing Dependency",
                "CustomTkinter is not installed.\n\nPlease install it with:\npip install customtkinter"
            )
        else:
            messagebox.showerror("Import Error", f"Missing dependency:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Application failed to start:\n{str(e)}")

if __name__ == "__main__":
    main()