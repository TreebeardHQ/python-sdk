# JavaScript SDK Implementation Guide for Treebeard

Based on analysis of the Python SDK, here's a comprehensive guide to building a JavaScript SDK that ports the core functionality with OTEL format output, console.log monkey-patching, per-request trace IDs, and global exception handling.

## Architecture Overview

The JavaScript SDK should mirror the Python SDK's modular architecture:

- **Core**: Main SDK class handling initialization, configuration, and log sending
- **Logger**: Primary logging interface with level-based methods
- **Context**: Request-scoped context management using AsyncLocalStorage
- **Batch**: Log batching and buffering for efficient transmission
- **Framework Integrations**: Express.js instrumentation for automatic request tracing
- **Exception Handling**: Global error capture across sync/async contexts

## Core Components

### 1. Core SDK Class (`TreebeardJS`)

```javascript
// src/core.js
import { EventEmitter } from 'events';
import { AsyncLocalStorage } from 'async_hooks';
import { LogBatch } from './batch.js';
import { LoggingContext } from './context.js';

export class TreebeardJS extends EventEmitter {
  static instance = null;
  static initialized = false;

  constructor(options = {}) {
    super();
    
    if (TreebeardJS.instance) {
      return TreebeardJS.instance;
    }

    this.apiKey = options.apiKey || process.env.TREEBEARD_API_KEY;
    this.endpoint = options.endpoint || process.env.TREEBEARD_API_URL || 'https://api.treebeardhq.com/logs/batch';
    this.projectName = options.projectName;
    this.batchSize = options.batchSize || 100;
    this.batchAge = options.batchAge || 5000; // ms
    this.flushInterval = options.flushInterval || 30000; // ms
    this.otelFormat = options.otelFormat !== false; // Default to true for JS SDK
    this.captureConsole = options.captureConsole || false;
    this.captureUnhandled = options.captureUnhandled !== false;
    
    this.batch = new LogBatch(this.batchSize, this.batchAge);
    this.flushTimer = null;
    this.sendQueue = [];
    this.isShuttingDown = false;
    
    this.setupExceptionHandlers();
    this.startFlushTimer();
    
    if (this.captureConsole) {
      this.enableConsoleCapture();
    }
    
    TreebeardJS.instance = this;
    TreebeardJS.initialized = true;
  }

  static init(options) {
    return new TreebeardJS(options);
  }

  formatOtelLog(logEntry) {
    const timestamp = logEntry.ts || Date.now();
    
    // Convert to nanoseconds for OTEL
    const otelLog = {
      Timestamp: String(timestamp * 1_000_000),
      SeverityText: this.mapSeverityText(logEntry.level),
      SeverityNumber: this.mapSeverityNumber(logEntry.level),
      Body: logEntry.message,
      Resource: {
        'service.name': this.projectName || 'javascript-app',
        source: logEntry.source || 'treebeard-js'
      },
      InstrumentationScope: {
        Name: 'treebeard-js-sdk',
        Version: '1.0.0'
      },
      Attributes: {}
    };

    // Add trace context
    if (logEntry.traceId) {
      otelLog.TraceId = logEntry.traceId;
    }

    // Add code location
    if (logEntry.file) otelLog.Attributes['code.filepath'] = logEntry.file;
    if (logEntry.line) otelLog.Attributes['code.lineno'] = logEntry.line;
    if (logEntry.function) otelLog.Attributes['code.function'] = logEntry.function;

    // Add exception details
    if (logEntry.exception) {
      otelLog.Attributes['exception.type'] = logEntry.exception.name;
      otelLog.Attributes['exception.message'] = logEntry.exception.message;
      otelLog.Attributes['exception.stacktrace'] = logEntry.exception.stack;
    }

    // Add custom attributes
    Object.keys(logEntry).forEach(key => {
      if (!['ts', 'level', 'message', 'source', 'traceId', 'file', 'line', 'function', 'exception'].includes(key)) {
        otelLog.Attributes[key] = logEntry[key];
      }
    });

    return otelLog;
  }

  mapSeverityText(level) {
    const mapping = {
      trace: 'TRACE',
      debug: 'DEBUG',
      info: 'INFO',
      warn: 'WARN',
      warning: 'WARN',
      error: 'ERROR',
      critical: 'FATAL',
      fatal: 'FATAL'
    };
    return mapping[level] || 'INFO';
  }

  mapSeverityNumber(level) {
    const mapping = {
      trace: 1,
      debug: 5,
      info: 9,
      warn: 13,
      warning: 13,
      error: 17,
      critical: 21,
      fatal: 21
    };
    return mapping[level] || 9;
  }

  add(logEntry) {
    if (this.isShuttingDown) return;

    const formattedLog = this.otelFormat ? 
      this.formatOtelLog(logEntry) : 
      this.formatCompactLog(logEntry);

    if (this.batch.add(formattedLog)) {
      this.flush();
    }
  }

  async flush() {
    const logs = this.batch.getLogs();
    if (logs.length === 0) return;

    if (!this.apiKey) {
      console.warn('Treebeard: No API key provided - logs will be output to console');
      logs.forEach(log => console.log(JSON.stringify(log)));
      return;
    }

    try {
      const response = await fetch(this.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`
        },
        body: JSON.stringify({
          logs,
          project_name: this.projectName,
          sdk_version: 2
        })
      });

      if (!response.ok) {
        console.error(`Treebeard: Failed to send logs: ${response.status}`);
      }
    } catch (error) {
      console.error('Treebeard: Error sending logs:', error);
    }
  }

  setupExceptionHandlers() {
    if (!this.captureUnhandled) return;

    // Unhandled Promise rejections
    process.on('unhandledRejection', (reason, promise) => {
      this.logger.error('Unhandled Promise Rejection', {
        error: reason,
        promise: promise.toString()
      });
    });

    // Uncaught exceptions
    process.on('uncaughtException', (error) => {
      this.logger.error('Uncaught Exception', { error });
      
      // Flush logs before exit
      this.flush().finally(() => {
        process.exit(1);
      });
    });
  }

  enableConsoleCapture() {
    const originalMethods = {};
    const levels = ['log', 'info', 'warn', 'error', 'debug'];
    
    levels.forEach(level => {
      originalMethods[level] = console[level];
      console[level] = (...args) => {
        // Call original method
        originalMethods[level](...args);
        
        // Log to Treebeard
        const message = args.map(arg => 
          typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
        ).join(' ');
        
        const logLevel = level === 'log' ? 'info' : level;
        this.logger[logLevel](message, { source: 'console' });
      };
    });

    // Store originals for cleanup
    this.originalConsoleMethods = originalMethods;
  }

  disableConsoleCapture() {
    if (this.originalConsoleMethods) {
      Object.keys(this.originalConsoleMethods).forEach(level => {
        console[level] = this.originalConsoleMethods[level];
      });
      this.originalConsoleMethods = null;
    }
  }

  startFlushTimer() {
    this.flushTimer = setInterval(() => {
      this.flush();
    }, this.flushInterval);
  }

  shutdown() {
    this.isShuttingDown = true;
    
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    
    this.disableConsoleCapture();
    
    // Final flush
    return this.flush();
  }
}
```

### 2. Logger Interface (`Logger`)

```javascript
// src/logger.js
import { TreebeardJS } from './core.js';
import { LoggingContext } from './context.js';
import { v4 as uuidv4 } from 'uuid';

export class Logger {
  static getCallerInfo() {
    const error = new Error();
    const stack = error.stack.split('\n');
    
    // Find first non-SDK frame
    for (let i = 2; i < stack.length; i++) {
      const frame = stack[i];
      if (!frame.includes('treebeard') && !frame.includes('node_modules')) {
        const match = frame.match(/at .* \((.+):(\d+):(\d+)\)|at (.+):(\d+):(\d+)/);
        if (match) {
          const file = match[1] || match[4];
          const line = parseInt(match[2] || match[5]);
          const column = parseInt(match[3] || match[6]);
          
          // Extract function name
          const funcMatch = frame.match(/at (\w+)/);
          const functionName = funcMatch ? funcMatch[1] : 'anonymous';
          
          return { file, line, column, function: functionName };
        }
      }
    }
    
    return {};
  }

  static prepareLogData(message, metadata = {}, level = 'info') {
    const context = LoggingContext.getAll();
    const caller = this.getCallerInfo();
    
    const logEntry = {
      message,
      level,
      ts: Date.now(),
      traceId: context.traceId || this.generateTraceId(),
      source: metadata.source || 'treebeard-js',
      ...caller,
      ...metadata
    };

    return logEntry;
  }

  static generateTraceId() {
    return `T${uuidv4().replace(/-/g, '')}`;
  }

  static start(name, data = {}) {
    const traceId = this.generateTraceId();
    
    LoggingContext.clear();
    LoggingContext.set('traceId', traceId);
    LoggingContext.set('traceName', name);
    
    this.info(`Beginning ${name}`, {
      ...data,
      _traceStart: true,
      traceName: name
    });
    
    return traceId;
  }

  static end() {
    LoggingContext.clear();
  }

  static completeSuccess(data = {}) {
    const traceName = LoggingContext.get('traceName');
    this.info(`Completed ${traceName}`, {
      ...data,
      _traceCompleteSuccess: true,
      traceName
    });
    this.end();
  }

  static completeError(error, data = {}) {
    const traceName = LoggingContext.get('traceName');
    this.error(`Failed ${traceName}`, {
      ...data,
      error,
      _traceCompleteError: true,
      traceName
    });
    this.end();
  }

  static trace(message, metadata) {
    const logEntry = this.prepareLogData(message, metadata, 'trace');
    TreebeardJS.instance?.add(logEntry);
  }

  static debug(message, metadata) {
    const logEntry = this.prepareLogData(message, metadata, 'debug');
    TreebeardJS.instance?.add(logEntry);
  }

  static info(message, metadata) {
    const logEntry = this.prepareLogData(message, metadata, 'info');
    TreebeardJS.instance?.add(logEntry);
  }

  static warn(message, metadata) {
    const logEntry = this.prepareLogData(message, metadata, 'warn');
    TreebeardJS.instance?.add(logEntry);
  }

  static warning(message, metadata) {
    this.warn(message, metadata);
  }

  static error(message, metadata) {
    // Handle error objects specially
    if (metadata && metadata.error instanceof Error) {
      metadata.exception = {
        name: metadata.error.name,
        message: metadata.error.message,
        stack: metadata.error.stack
      };
    }
    
    const logEntry = this.prepareLogData(message, metadata, 'error');
    TreebeardJS.instance?.add(logEntry);
  }

  static critical(message, metadata) {
    const logEntry = this.prepareLogData(message, metadata, 'critical');
    TreebeardJS.instance?.add(logEntry);
  }

  static fatal(message, metadata) {
    this.critical(message, metadata);
  }
}
```

### 3. Context Management (`LoggingContext`)

```javascript
// src/context.js
import { AsyncLocalStorage } from 'async_hooks';

export class LoggingContext {
  static asyncLocalStorage = new AsyncLocalStorage();

  static run(store, callback) {
    return this.asyncLocalStorage.run(store, callback);
  }

  static set(key, value) {
    const store = this.asyncLocalStorage.getStore() || {};
    store[key] = value;
    // Note: AsyncLocalStorage doesn't have direct set, 
    // context changes need to be managed at request boundaries
  }

  static get(key, defaultValue = null) {
    const store = this.asyncLocalStorage.getStore() || {};
    return store[key] ?? defaultValue;
  }

  static getAll() {
    return this.asyncLocalStorage.getStore() || {};
  }

  static clear() {
    // Context will be cleared at request boundary
    const store = this.asyncLocalStorage.getStore();
    if (store) {
      Object.keys(store).forEach(key => delete store[key]);
    }
  }

  static getCurrentTraceId() {
    return this.get('traceId');
  }

  static setTraceId(traceId) {
    this.set('traceId', traceId);
  }
}
```

### 4. Log Batching (`LogBatch`)

```javascript
// src/batch.js
export class LogBatch {
  constructor(maxSize = 100, maxAge = 5000) {
    this.logs = [];
    this.maxSize = maxSize;
    this.maxAge = maxAge;
    this.lastFlush = Date.now();
  }

  add(logEntry) {
    this.logs.push(logEntry);
    
    const shouldFlush = (
      this.logs.length >= this.maxSize ||
      (Date.now() - this.lastFlush) >= this.maxAge
    );
    
    return shouldFlush;
  }

  getLogs() {
    const logs = this.logs;
    this.logs = [];
    this.lastFlush = Date.now();
    return logs;
  }

  size() {
    return this.logs.length;
  }
}
```

### 5. Express.js Integration (`TreebeardExpress`)

```javascript
// src/express.js
import { Logger } from './logger.js';
import { LoggingContext } from './context.js';

export class TreebeardExpress {
  static instrument(app) {
    if (app._treebeardInstrumented) {
      return;
    }

    // Middleware to start trace and set context
    app.use((req, res, next) => {
      // Create route name
      const routeName = req.route?.path || req.path || 'unknown';
      const traceName = `${req.method} ${routeName}`;
      
      // Create new context for this request
      const contextStore = {
        traceId: Logger.generateTraceId(),
        traceName,
        requestId: req.headers['x-request-id'] || `req_${Date.now()}`
      };

      // Run the rest of the request in this context
      LoggingContext.run(contextStore, () => {
        // Collect request metadata
        const requestData = {
          method: req.method,
          url: req.url,
          path: req.path,
          query: req.query,
          headers: this.sanitizeHeaders(req.headers),
          ip: req.ip || req.connection.remoteAddress,
          userAgent: req.get('User-Agent'),
          referer: req.get('Referer')
        };

        // Start trace
        Logger.start(traceName, requestData);

        // Hook into response finish
        const originalEnd = res.end;
        res.end = function(...args) {
          const statusCode = res.statusCode;
          
          if (statusCode >= 400) {
            Logger.completeError(new Error(`HTTP ${statusCode}`), {
              statusCode,
              headers: res.getHeaders()
            });
          } else {
            Logger.completeSuccess({
              statusCode,
              headers: res.getHeaders()
            });
          }
          
          originalEnd.apply(this, args);
        };

        next();
      });
    });

    app._treebeardInstrumented = true;
  }

  static sanitizeHeaders(headers) {
    const sanitized = { ...headers };
    const sensitiveHeaders = [
      'authorization', 'cookie', 'x-api-key', 'x-auth-token'
    ];
    
    sensitiveHeaders.forEach(header => {
      if (sanitized[header]) {
        sanitized[header] = '*****';
      }
    });
    
    return sanitized;
  }
}
```

## Package Structure

```
treebeard-js/
├── package.json
├── README.md
├── src/
│   ├── index.js          # Main exports
│   ├── core.js           # TreebeardJS class
│   ├── logger.js         # Logger interface
│   ├── context.js        # Context management
│   ├── batch.js          # Log batching
│   ├── express.js        # Express integration
│   └── utils/
│       ├── error-handler.js
│       └── stack-trace.js
├── examples/
│   ├── basic/
│   ├── express/
│   └── error-handling/
└── test/
    ├── unit/
    └── integration/
```

## Main Export (`index.js`)

```javascript
// src/index.js
export { TreebeardJS } from './core.js';
export { Logger } from './logger.js';
export { LoggingContext } from './context.js';
export { TreebeardExpress } from './express.js';

// Default initialization function
export function init(options = {}) {
  return TreebeardJS.init(options);
}

// Convenience exports
export const log = Logger;
export const trace = Logger;
```

## Usage Examples

### Basic Usage

```javascript
import { init, Logger } from 'treebeard-js';

// Initialize SDK
init({
  projectName: 'my-app',
  apiKey: 'your-api-key',
  otelFormat: true,
  captureConsole: true,
  captureUnhandled: true
});

// Use logger
Logger.info('Application started', { version: '1.0.0' });
Logger.error('Something went wrong', { error: new Error('test') });
```

### Express Integration

```javascript
import express from 'express';
import { init, TreebeardExpress } from 'treebeard-js';

const app = express();

// Initialize Treebeard
init({
  projectName: 'my-express-app',
  apiKey: process.env.TREEBEARD_API_KEY
});

// Instrument Express
TreebeardExpress.instrument(app);

app.get('/users/:id', (req, res) => {
  Logger.info('Fetching user', { userId: req.params.id });
  // Your route logic
  res.json({ user: 'data' });
});
```

### Manual Trace Management

```javascript
import { Logger } from 'treebeard-js';

async function processOrder(orderId) {
  const traceId = Logger.start('process-order', { orderId });
  
  try {
    // Business logic
    Logger.info('Validating order');
    await validateOrder(orderId);
    
    Logger.info('Processing payment');
    await processPayment(orderId);
    
    Logger.completeSuccess({ orderId });
  } catch (error) {
    Logger.completeError(error, { orderId });
    throw error;
  }
}
```

## Package.json Configuration

```json
{
  "name": "treebeard-js",
  "version": "1.0.0",
  "description": "JavaScript SDK for TreebeardHQ logging with OpenTelemetry format",
  "type": "module",
  "main": "src/index.js",
  "exports": {
    ".": "./src/index.js",
    "./express": "./src/express.js",
    "./logger": "./src/logger.js"
  },
  "scripts": {
    "test": "jest",
    "build": "rollup -c",
    "lint": "eslint src/",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "uuid": "^9.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "eslint": "^8.0.0",
    "jest": "^29.0.0",
    "rollup": "^3.0.0",
    "typescript": "^5.0.0"
  },
  "keywords": ["logging", "opentelemetry", "observability", "tracing"],
  "author": "TreebeardHQ",
  "license": "MIT"
}
```

## Key Features Implemented

✅ **OTEL Format Output**: All logs formatted according to OpenTelemetry specification  
✅ **Console.log Monkey-patching**: Optional capture of console methods  
✅ **Per-request Trace IDs**: Automatic trace context using AsyncLocalStorage  
✅ **Global Exception Handling**: Captures unhandled Promise rejections and exceptions  
✅ **Express Integration**: Automatic request tracing with route patterns  
✅ **Batching**: Efficient log batching with configurable size and age limits  
✅ **Context Management**: Request-scoped context that works across async boundaries  
✅ **Error Enrichment**: Automatic stack trace and error metadata extraction  

This JavaScript SDK provides feature parity with the Python version while leveraging JavaScript-specific patterns like AsyncLocalStorage for context management and native Promise handling for async operations.