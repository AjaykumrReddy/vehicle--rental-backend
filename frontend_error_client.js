// Frontend Error Reporting Client
class ErrorReporter {
    constructor(apiBaseUrl, userId = null, sessionId = null) {
        this.apiBaseUrl = apiBaseUrl;
        this.userId = userId;
        this.sessionId = sessionId || this.generateSessionId();
        this.setupGlobalErrorHandlers();
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    setupGlobalErrorHandlers() {
        // Catch JavaScript errors
        window.addEventListener('error', (event) => {
            this.reportError({
                error_message: event.message,
                error_code: 'JS_ERROR',
                stack_trace: event.error?.stack,
                page_url: window.location.href,
                metadata: {
                    filename: event.filename,
                    line_number: event.lineno,
                    column_number: event.colno
                }
            });
        });

        // Catch unhandled promise rejections
        window.addEventListener('unhandledrejection', (event) => {
            this.reportError({
                error_message: event.reason?.message || 'Unhandled Promise Rejection',
                error_code: 'PROMISE_REJECTION',
                stack_trace: event.reason?.stack,
                page_url: window.location.href,
                metadata: {
                    promise_rejection: true,
                    reason: event.reason
                }
            });
        });
    }

    // Report API call failures
    reportApiError(endpoint, method, status, errorMessage, requestData = null) {
        this.reportError({
            error_message: `API Error: ${errorMessage}`,
            error_code: 'API_CALL_FAILED',
            page_url: window.location.href,
            metadata: {
                endpoint,
                method,
                status,
                request_data: requestData,
                api_error: true
            }
        });
    }

    // Report third-party service errors
    reportThirdPartyError(serviceName, errorMessage, errorCode = null) {
        this.reportError({
            error_message: `${serviceName}: ${errorMessage}`,
            error_code: errorCode || 'THIRD_PARTY_ERROR',
            page_url: window.location.href,
            metadata: {
                service_name: serviceName,
                third_party_error: true
            }
        });
    }

    // Generic error reporting
    async reportError(errorData) {
        try {
            const payload = {
                ...errorData,
                user_id: this.userId,
                session_id: this.sessionId,
                timestamp: new Date().toISOString(),
                user_agent: navigator.userAgent,
                page_url: errorData.page_url || window.location.href
            };

            await fetch(`${this.apiBaseUrl}/error-audit/ui-error`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

        } catch (err) {
            // Fallback: log to console if error reporting fails
            console.error('Failed to report error:', err);
            console.error('Original error:', errorData);
        }
    }

    // Update user context
    setUser(userId) {
        this.userId = userId;
    }
}

// Usage Examples:

// Initialize error reporter
const errorReporter = new ErrorReporter('http://localhost:8000', 'user_123');

// Example: Reporting API failures
async function makeApiCall(endpoint, data) {
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            // Report API error
            errorReporter.reportApiError(
                endpoint,
                'POST',
                response.status,
                `HTTP ${response.status}: ${response.statusText}`,
                data
            );
            throw new Error(`API call failed: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        // Report network or other errors
        errorReporter.reportApiError(
            endpoint,
            'POST',
            0,
            error.message,
            data
        );
        throw error;
    }
}

// Example: Reporting third-party service errors
function initializeGoogleMaps() {
    try {
        // Google Maps initialization
        if (!window.google) {
            throw new Error('Google Maps API not loaded');
        }
        // ... map initialization code
    } catch (error) {
        errorReporter.reportThirdPartyError(
            'Google Maps',
            error.message,
            'MAPS_INIT_ERROR'
        );
    }
}

// Example: Manual error reporting
function handleCustomError(error) {
    errorReporter.reportError({
        error_message: error.message,
        error_code: 'CUSTOM_ERROR',
        stack_trace: error.stack,
        metadata: {
            custom_context: 'user_action_failed',
            additional_info: 'any relevant data'
        }
    });
}

export default ErrorReporter;