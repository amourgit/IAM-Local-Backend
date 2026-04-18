from typing import Dict, Optional, Any
from user_agents import parse as parse_user_agent
import hashlib
import logging

logger = logging.getLogger(__name__)

class DeviceAnalysisService:
    """
    Service d'analyse détaillée des devices à partir du User-Agent
    Fournit des informations complètes sur le device, OS et navigateur
    """

    @staticmethod
    def analyze_user_agent(user_agent_string: str) -> Dict[str, Any]:
        """
        Analyse complète du User-Agent

        Args:
            user_agent_string: Chaîne User-Agent brute

        Returns:
            Dictionnaire avec toutes les informations du device
        """
        try:
            if not user_agent_string or not user_agent_string.strip():
                return DeviceAnalysisService._get_empty_device_info()

            user_agent = parse_user_agent(user_agent_string)

            return {
                'device_id': DeviceAnalysisService._generate_device_id(user_agent_string),

                # Informations device
                'device_family': user_agent.device.family,
                'device_brand': user_agent.device.brand,
                'device_model': user_agent.device.model,
                'device_type': DeviceAnalysisService._normalize_device_type(user_agent),

                # Informations OS
                'os_family': user_agent.os.family,
                'os_version': user_agent.os.version_string,

                # Informations navigateur
                'browser_family': user_agent.browser.family,
                'browser_version': user_agent.browser.version_string,

                # Métadonnées
                'is_mobile': user_agent.is_mobile,
                'is_tablet': user_agent.is_tablet,
                'is_pc': user_agent.is_pc,
                'is_bot': user_agent.is_bot,
                'is_email_client': user_agent.is_email_client,

                # Chaîne originale
                'user_agent_string': user_agent_string
            }

        except Exception as e:
            logger.warning(f"Erreur lors de l'analyse du User-Agent '{user_agent_string}': {e}")
            return DeviceAnalysisService._get_fallback_device_info(user_agent_string)

    @staticmethod
    def _generate_device_id(user_agent_string: str) -> str:
        """
        Génère un ID unique pour le device basé sur le User-Agent
        """
        # Hash du User-Agent pour créer un ID déterministe
        return hashlib.md5(user_agent_string.encode('utf-8')).hexdigest()

    @staticmethod
    def _normalize_device_type(user_agent) -> str:
        """
        Normalise le type de device
        """
        if user_agent.is_mobile:
            return 'mobile'
        elif user_agent.is_tablet:
            return 'tablet'
        elif user_agent.is_pc:
            return 'desktop'
        elif user_agent.is_bot:
            return 'bot'
        else:
            return 'other'

    @staticmethod
    def _get_empty_device_info() -> Dict[str, Any]:
        """
        Retourne des informations vides pour les User-Agents manquants
        """
        return {
            'device_id': 'unknown',
            'device_family': 'Unknown',
            'device_brand': 'Unknown',
            'device_model': 'Unknown',
            'device_type': 'other',
            'os_family': 'Unknown',
            'os_version': 'Unknown',
            'browser_family': 'Unknown',
            'browser_version': 'Unknown',
            'is_mobile': False,
            'is_tablet': False,
            'is_pc': False,
            'is_bot': False,
            'is_email_client': False,
            'user_agent_string': ''
        }

    @staticmethod
    def _get_fallback_device_info(user_agent_string: str) -> Dict[str, Any]:
        """
        Retourne des informations de fallback en cas d'erreur d'analyse
        """
        return {
            'device_id': DeviceAnalysisService._generate_device_id(user_agent_string),
            'device_family': 'Unknown',
            'device_brand': 'Unknown',
            'device_model': 'Unknown',
            'device_type': 'other',
            'os_family': 'Unknown',
            'os_version': 'Unknown',
            'browser_family': 'Unknown',
            'browser_version': 'Unknown',
            'is_mobile': False,
            'is_tablet': False,
            'is_pc': False,
            'is_bot': False,
            'is_email_client': False,
            'user_agent_string': user_agent_string
        }

    @staticmethod
    def get_device_summary(device_info: Dict[str, Any]) -> str:
        """
        Génère un résumé lisible du device
        """
        parts = []

        # Device
        if device_info.get('device_brand') and device_info['device_brand'] != 'Unknown':
            device_part = device_info['device_brand']
            if device_info.get('device_model') and device_info['device_model'] != 'Unknown':
                device_part += f" {device_info['device_model']}"
            parts.append(device_part)
        elif device_info.get('device_family') and device_info['device_family'] != 'Unknown':
            parts.append(device_info['device_family'])

        # OS
        if device_info.get('os_family') and device_info['os_family'] != 'Unknown':
            os_part = device_info['os_family']
            if device_info.get('os_version') and device_info['os_version'] != 'Unknown':
                os_part += f" {device_info['os_version']}"
            parts.append(os_part)

        # Browser
        if device_info.get('browser_family') and device_info['browser_family'] != 'Unknown':
            browser_part = device_info['browser_family']
            if device_info.get('browser_version') and device_info['browser_version'] != 'Unknown':
                browser_part += f" {device_info['browser_version']}"
            parts.append(browser_part)

        if not parts:
            return f"{device_info.get('device_type', 'Unknown').title()} Device"

        return " - ".join(parts)

    @staticmethod
    def compare_device_info(old_info: Dict[str, Any], new_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare deux analyses de device et retourne les différences
        """
        differences = {}

        keys_to_compare = [
            'device_family', 'device_brand', 'device_model', 'device_type',
            'os_family', 'os_version', 'browser_family', 'browser_version'
        ]

        for key in keys_to_compare:
            old_value = old_info.get(key)
            new_value = new_info.get(key)

            if old_value != new_value:
                differences[key] = {
                    'old': old_value,
                    'new': new_value
                }

        return differences

    @staticmethod
    def is_same_device(info1: Dict[str, Any], info2: Dict[str, Any]) -> bool:
        """
        Détermine si deux analyses correspondent au même device
        """
        return info1.get('device_id') == info2.get('device_id')

    @staticmethod
    def get_device_category(device_info: Dict[str, Any]) -> str:
        """
        Retourne la catégorie du device pour les statistiques
        """
        device_type = device_info.get('device_type', 'other')

        if device_type == 'mobile':
            return 'Mobile'
        elif device_type == 'tablet':
            return 'Tablet'
        elif device_type == 'desktop':
            return 'Desktop'
        elif device_type == 'bot':
            return 'Bot'
        else:
            return 'Other'

    @staticmethod
    def get_os_category(device_info: Dict[str, Any]) -> str:
        """
        Retourne la catégorie du système d'exploitation
        """
        os_family = device_info.get('os_family', 'Unknown')

        if 'Windows' in os_family:
            return 'Windows'
        elif 'macOS' in os_family or 'Mac OS' in os_family:
            return 'macOS'
        elif 'Linux' in os_family:
            return 'Linux'
        elif 'Android' in os_family:
            return 'Android'
        elif 'iOS' in os_family:
            return 'iOS'
        else:
            return 'Other'

    @staticmethod
    def get_browser_category(device_info: Dict[str, Any]) -> str:
        """
        Retourne la catégorie du navigateur
        """
        browser_family = device_info.get('browser_family', 'Unknown')

        if 'Chrome' in browser_family:
            return 'Chrome'
        elif 'Firefox' in browser_family:
            return 'Firefox'
        elif 'Safari' in browser_family:
            return 'Safari'
        elif 'Edge' in browser_family:
            return 'Edge'
        elif 'Opera' in browser_family:
            return 'Opera'
        else:
            return 'Other'