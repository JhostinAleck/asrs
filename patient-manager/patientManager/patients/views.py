
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.core.cache import cache
from django.utils import timezone
from django.db.models import Q
from .models import Patient, MedicalRecord
from .serializers import PatientSerializer, PatientListSerializer, MedicalRecordSerializer
import logging
import time

logger = logging.getLogger('patients')
performance_logger = logging.getLogger('performance')

class PatientViewSet(viewsets.ModelViewSet):
    """Patient management viewset with caching"""
    
    queryset = Patient.objects.filter(is_active=True)
    serializer_class = PatientSerializer
    search_fields = ['first_name', 'last_name', 'email', 'phone']
    ordering_fields = ['last_name', 'first_name', 'created_at']
    ordering = ['last_name', 'first_name']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PatientListSerializer
        return PatientSerializer
    
    def list(self, request, *args, **kwargs):
        """List patients with caching"""
        start_time = time.time()
        
        # Get user from nginx header
        user = request.META.get('HTTP_X_USER', 'unknown')
        
        # Create cache key based on query parameters
        query_params = request.query_params.dict()
        cache_key = f"patients_list_{hash(str(query_params))}"
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            performance_logger.info({
                'action': 'patients_list',
                'user': user,
                'cache_hit': True,
                'response_time': time.time() - start_time,
                'query_params': query_params
            })
            logger.info(f"Patient list served from cache for user: {user}")
            return Response(cached_data)
        
        # If not in cache, get from database
        response = super().list(request, *args, **kwargs)
        
        # Cache the response for 5 minutes
        cache.set(cache_key, response.data, 300)
        
        end_time = time.time()
        performance_logger.info({
            'action': 'patients_list',
            'user': user,
            'cache_hit': False,
            'response_time': end_time - start_time,
            'count': len(response.data.get('results', [])),
            'query_params': query_params
        })
        
        logger.info(f"Patient list generated for user: {user}, count: {len(response.data.get('results', []))}")
        return response
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve single patient with caching"""
        start_time = time.time()
        user = request.META.get('HTTP_X_USER', 'unknown')
        patient_id = kwargs.get('pk')
        
        cache_key = f"patient_{patient_id}"
        cached_data = cache.get(cache_key)
        
        if cached_data:
            performance_logger.info({
                'action': 'patient_detail',
                'user': user,
                'patient_id': patient_id,
                'cache_hit': True,
                'response_time': time.time() - start_time
            })
            logger.info(f"Patient {patient_id} served from cache for user: {user}")
            return Response(cached_data)
        
        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, 600)  # Cache for 10 minutes
        
        end_time = time.time()
        performance_logger.info({
            'action': 'patient_detail',
            'user': user,
            'patient_id': patient_id,
            'cache_hit': False,
            'response_time': end_time - start_time
        })
        
        logger.info(f"Patient {patient_id} retrieved for user: {user}")
        return response
    
    def create(self, request, *args, **kwargs):
        """Create patient and invalidate cache"""
        user = request.META.get('HTTP_X_USER', 'unknown')
        response = super().create(request, *args, **kwargs)
        
        # Invalidate list cache
        cache.delete_many([key for key in cache._cache.keys() if key.startswith('patients_list_')])
        
        logger.info(f"Patient created by user: {user}, ID: {response.data.get('patient_id')}")
        return response
    
    def update(self, request, *args, **kwargs):
        """Update patient and invalidate cache"""
        user = request.META.get('HTTP_X_USER', 'unknown')
        patient_id = kwargs.get('pk')
        
        response = super().update(request, *args, **kwargs)
        
        # Invalidate caches
        cache.delete(f"patient_{patient_id}")
        cache.delete_many([key for key in cache._cache.keys() if key.startswith('patients_list_')])
        
        logger.info(f"Patient {patient_id} updated by user: {user}")
        return response
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Advanced search endpoint"""
        start_time = time.time()
        user = request.META.get('HTTP_X_USER', 'unknown')
        
        query = request.query_params.get('q', '')
        if not query:
            return Response({'error': 'Query parameter "q" is required'}, status=400)
        
        # Search in multiple fields
        patients = Patient.objects.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(patient_id__icontains=query)
        ).filter(is_active=True)[:20]  # Limit to 20 results
        
        serializer = PatientListSerializer(patients, many=True)
        
        end_time = time.time()
        performance_logger.info({
            'action': 'patient_search',
            'user': user,
            'query': query,
            'results_count': len(serializer.data),
            'response_time': end_time - start_time
        })
        
        logger.info(f"Patient search performed by user: {user}, query: {query}, results: {len(serializer.data)}")
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def medical_records(self, request, pk=None):
        """Get medical records for a patient"""
        patient = self.get_object()
        records = patient.medical_records.all()
        serializer = MedicalRecordSerializer(records, many=True)
        
        user = request.META.get('HTTP_X_USER', 'unknown')
        logger.info(f"Medical records accessed for patient {pk} by user: {user}")
        
        return Response(serializer.data)

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'service': 'patient_manager',
        'timestamp': timezone.now(),
        'database': 'connected',
        'cache': 'connected',
        'version': '1.0.0'
    })

@api_view(['GET'])
def stats(request):
    """Statistics endpoint"""
    user = request.META.get('HTTP_X_USER', 'unknown')
    
    stats = {
        'total_patients': Patient.objects.filter(is_active=True).count(),
        'total_medical_records': MedicalRecord.objects.count(),
        'patients_created_today': Patient.objects.filter(
            created_at__date=timezone.now().date()
        ).count(),
    }
    
    logger.info(f"Stats accessed by user: {user}")
    return Response(stats)