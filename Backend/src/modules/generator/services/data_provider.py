import random
import string
import time
import uuid
from typing import Any, Dict, Optional

class DataProviderService:
    """
    Centralized service for generating realistic test data.
    """
    
    @staticmethod
    def generate_email(prefix: str = "test", domain: str = "example.com") -> str:
        timestamp = int(time.time() * 1000)
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        return f"{prefix}_{timestamp}_{random_suffix}@{domain}"
    
    @staticmethod
    def generate_password() -> str:
        return "Test@123!"
    
    @staticmethod
    def generate_name() -> str:
        first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona"]
        last_names = ["Doe", "Smith", "Johnson", "Brown", "Taylor", "Miller", "Wilson"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    @staticmethod
    def generate_username(prefix: str = "user") -> str:
        timestamp = int(time.time()) % 100000
        return f"{prefix}_{timestamp}"

    @staticmethod
    def get_sample_value(field_name: str, field_type: str = "string", schema: Dict[str, Any] = None) -> Any:
        """
        Generate a realistic value based on the field name and type.
        """
        field_name_lower = field_name.lower()
        
        # Handle Enums
        if schema and "enum" in schema:
            return schema["enum"][0]
            
        # Specific patterns
        if "email" in field_name_lower:
            return DataProviderService.generate_email()
        if any(kw in field_name_lower for kw in ("password", "passcode", "secret")):
            return DataProviderService.generate_password()
        if any(kw in field_name_lower for kw in ("username", "login")):
            return DataProviderService.generate_username()
        if "name" in field_name_lower:
            return DataProviderService.generate_name()
        if "phone" in field_name_lower or "mobile" in field_name_lower:
            return "+1" + "".join(random.choices(string.digits, k=10))
        if any(kw in field_name_lower for kw in ("url", "link", "image", "photo", "avatar", "picture", "logo")):
            return "https://via.placeholder.com/300"
        if "address" in field_name_lower:
            return "123 Main St, Springfield"
        if "city" in field_name_lower:
            return "Springfield"
        if "country" in field_name_lower:
            return "USA"
        if "zip" in field_name_lower or "postal" in field_name_lower:
            return "62704"
            
        # Type-based defaults
        if field_type == "integer":
            return 1
        if field_type == "number":
            return 1.0
        if field_type == "boolean":
            return True
        if field_type == "array":
            return []
        if field_type == "object":
            return {}
            
        return f"test_{field_name}"

data_provider = DataProviderService()
