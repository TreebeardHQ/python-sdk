import inspect
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from .constants import TRACE_ID_KEY, MESSAGE_KEY, FILE_KEY, LINE_KEY, TRACEBACK_KEY
from ..log import Log
from ..context import LoggingContext


def _prepare_log_data(message: str, data: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
    """Prepare log data by merging context, provided data and kwargs.

        Args:
            message: The log message
            data: Optional dictionary of metadata
            **kwargs: Additional metadata as keyword arguments

        Returns:
            Dict containing the complete log entry
        """

    frame = inspect.stack()[2]  # 0: this func, 1: SDK wrapper, 2: user
    filename = frame.filename
    line_number = frame.lineno

     # Start with the context data
     log_data = LoggingContext.get_all()

      # Add the message
      log_data[MESSAGE_KEY] = message

       if not log_data.get(TRACE_ID_KEY):
            trace_id = Log.start()
            log_data[TRACE_ID_KEY] = trace_id

        # Merge explicit data dict if provided
        if data is not None:
            log_data.update(data)

        # Merge kwargs
        if kwargs:
            log_data.update(kwargs)

        # Create a new dictionary to avoid modifying in place
        processed_data = {}
        processed_data[FILE_KEY] = filename
        processed_data[LINE_KEY] = line_number

        masked_terms = {
            'password', 'pass', 'pw', 'secret', 'api_key', 'access_token', 'refresh_token',
            'token', 'key', 'auth', 'credentials', 'credential', 'private_key', 'public_key',
            'ssh_key', 'certificate', 'cert', 'signature', 'sign', 'hash', 'salt', 'nonce',
            'session_id', 'session', 'cookie', 'jwt', 'bearer', 'oauth', 'oauth2', 'openid',
            'client_id', 'client_secret', 'consumer_key', 'consumer_secret', 'aws_access_key',
            'aws_secret_key', 'aws_session_token', 'azure_key', 'gcp_key', 'api_secret',
            'encryption_key', 'decryption_key', 'master_key', 'root_key', 'admin_key',
            'database_password', 'db_password', 'db_pass', 'redis_password', 'redis_pass',
            'mongodb_password', 'mongodb_pass', 'postgres_password', 'postgres_pass',
            'mysql_password', 'mysql_pass', 'oracle_password', 'oracle_pass'
        }

        for key, value in log_data.items():

            if value is None:
                continue

            if isinstance(value, Exception):
                if value.__traceback__ is not None:
                    processed_data[TRACEBACK_KEY] = '\n'.join(traceback.format_exception(
                        type(value), value, value.__traceback__))
                    tb = value.__traceback__
                    while tb.tb_next:  # walk to the last frame
                        tb = tb.tb_next

                    processed_data[FILE_KEY] = tb.tb_frame.f_code.co_filename
                    processed_data[LINE_KEY] = tb.tb_lineno
                else:
                    processed_data[TRACEBACK_KEY] = str(value)

            # Handle datetime objects
            elif isinstance(value, datetime):
                processed_data[key] = int(value.timestamp())
            # Handle dictionaries
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, (int, float, str, bool, type(None))):
                        # Mask password-related keys
                        if any(pw_key in k.lower() for pw_key in masked_terms):
                            processed_data[f"{key}_{k}"] = '*****'
                        else:
                            processed_data[f"{key}_{k}"] = v
            # Handle objects
            elif isinstance(value, object) and not isinstance(value, (int, float, str, bool, type(None))):
                for attr_name in dir(value):
                    if not attr_name.startswith("_"):
                        try:
                            attr_value = getattr(value, attr_name)
                            if isinstance(attr_value, (int, float, str, bool, type(None))):
                                # Mask password-related keys
                                if any(pw_key in attr_name.lower() for pw_key in masked_terms):
                                    processed_data[f"{key}_{attr_name}"] = '*****'
                                else:
                                    processed_data[f"{key}_{attr_name}"] = attr_value
                        except:
                            continue
            # Keep all primitive types as is
            else:
                # Mask password-related keys
                if any(pw_key in key.lower() for pw_key in masked_terms):
                    processed_data[key] = '*****'
                else:
                    processed_data[key] = value

        return processed_data
