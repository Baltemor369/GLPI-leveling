"""Extensions Flask partagées — instanciées ici, initialisées dans create_app()."""
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

csrf    = CSRFProtect()
# storage_uri="memory://" = par worker (4 workers = 40 req/min max brute force).
# Acceptable pour un déploiement interne 10-50 users sans Redis.
limiter = Limiter(key_func=get_remote_address, default_limits=[], storage_uri="memory://")
