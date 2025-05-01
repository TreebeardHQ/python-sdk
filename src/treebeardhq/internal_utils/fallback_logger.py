"""
Fallback logger for Treebeard.
"""
import logging

fallback_logger = logging.getLogger('treebeard')
fallback_logger.propagate = False
if not fallback_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    fallback_logger.addHandler(handler)

fallback_logger.setLevel(logging.INFO)


sdk_logger = logging.getLogger('treebeard.sdk')
sdk_logger.propagate = False
if not sdk_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)-7s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    sdk_logger.addHandler(handler)

sdk_logger.setLevel(logging.INFO)
