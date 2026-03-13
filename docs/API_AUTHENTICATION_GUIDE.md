# API Authentication Guide

## Overview

The Autonomous Software Foundry API uses API key-based authentication to secure endpoints. This guide explains how to create, manage, and use API keys.

## API Key Format

API keys follow the format: `asf_<random_string>`

Example: `asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456`

## Creating an API Key

### Endpoint
```
POST /api-keys
```

### Request Body
```json
{
  "name": "My API Key",
  "expires_in_days": 90,
  "rate_limit_per_minute": 100
}
```

### Parameters
- `name` (required): Human-readable name for the key
- `expires_in_days` (optional): Days until expiration (1-365)
- `rate_limit_per_minute` (optional): Max requests per minute (default: 60)

### Response
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "My API Key",
  "key": "asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456",
  "key_prefix": "asf_AbCd",
  "expires_at": "2024-04-15T10:00:00Z",
  "rate_limit_per_minute": 100,
  "created_at": "2024-01-15T10:00:00Z"
}
```

⚠️ **Important**: The `key` field is only returned once during creation. Store it securely - you cannot retrieve it later.

## Using an API Key

Include the API key in the `X-API-Key` header:

```bash
curl -X GET http://localhost:8000/projects \
  -H "X-API-Key: asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
```

### Python Example
```python
import requests

api_key = "asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456"
headers = {"X-API-Key": api_key}

response = requests.get("http://localhost:8000/projects", headers=headers)
print(response.json())
```

### JavaScript Example
```javascript
const apiKey = "asf_AbCdEfGhIjKlMnOpQrStUvWxYz123456";

fetch("http://localhost:8000/projects", {
  headers: {
    "X-API-Key": apiKey
  }
})
  .then(response => response.json())
  .then(data => console.log(data));
```

## Managing API Keys

### List All API Keys

```bash
GET /api-keys
```

Returns all API keys (without the actual key values):

```json
[
  {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "name": "My API Key",
    "key_prefix": "asf_AbCd",
    "is_active": true,
    "expires_at": "2024-04-15T10:00:00Z",
    "last_used_at": "2024-01-15T10:30:00Z",
    "rate_limit_per_minute": 100,
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

### Deactivate an API Key

Deactivate without deleting (can be reactivated later):

```bash
PATCH /api-keys/{key_id}/deactivate
```

### Delete an API Key

Permanently delete an API key:

```bash
DELETE /api-keys/{key_id}
```

## Rate Limiting

### Default Limits
- **Default**: 60 requests per minute
- **Configurable**: Set custom limits per API key

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1705320000
```

### Rate Limit Exceeded

When you exceed the rate limit, you'll receive a 429 response:

```json
{
  "detail": "Rate limit exceeded. Try again in 30 seconds",
  "error_code": "http_429",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

Headers:
```
Retry-After: 30
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705320030
```

## Security Best Practices

### 1. Store Keys Securely
- Never commit API keys to version control
- Use environment variables or secret management systems
- Rotate keys regularly

### 2. Use Expiration
- Set expiration dates for API keys
- Rotate keys before expiration
- Use shorter expiration for high-privilege keys

### 3. Monitor Usage
- Check `last_used_at` timestamps
- Deactivate unused keys
- Review rate limit usage

### 4. Principle of Least Privilege
- Create separate keys for different applications
- Use appropriate rate limits
- Deactivate keys when no longer needed

## Error Responses

### Invalid API Key
```json
{
  "detail": "Invalid API key",
  "error_code": "http_401",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Expired API Key
```json
{
  "detail": "API key is inactive or expired",
  "error_code": "http_401",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Missing API Key
```json
{
  "detail": "API key required",
  "error_code": "http_401",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Key Rotation

To rotate an API key:

1. Create a new API key
2. Update your applications to use the new key
3. Verify the new key works
4. Deactivate or delete the old key

```bash
# 1. Create new key
curl -X POST http://localhost:8000/api-keys \
  -H "Content-Type: application/json" \
  -d '{"name": "New Production Key", "expires_in_days": 90}'

# 2. Test new key
curl -X GET http://localhost:8000/projects \
  -H "X-API-Key: <new_key>"

# 3. Deactivate old key
curl -X PATCH http://localhost:8000/api-keys/<old_key_id>/deactivate
```

## Environment Variables

Configure authentication behavior:

```bash
# .env file
ENABLE_API_KEY_AUTH=true
DEFAULT_RATE_LIMIT_PER_MINUTE=60
API_KEY_EXPIRATION_DAYS=90
```

## Troubleshooting

### "Invalid API key" Error
- Verify the key is correct (check for typos)
- Ensure the key hasn't been deactivated
- Check if the key has expired

### Rate Limit Issues
- Check `X-RateLimit-Remaining` header
- Wait for `Retry-After` seconds
- Consider requesting a higher rate limit

### Key Not Working After Creation
- Ensure you're using the `X-API-Key` header
- Verify the header name is correct (case-sensitive)
- Check that the key was copied completely

## API Reference

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api-keys` | Create new API key |
| GET | `/api-keys` | List all API keys |
| DELETE | `/api-keys/{key_id}` | Delete API key |
| PATCH | `/api-keys/{key_id}/deactivate` | Deactivate API key |

### Authentication Header

```
X-API-Key: asf_<your_api_key>
```

## Support

For issues or questions:
- Check the [API documentation](http://localhost:8000/docs)
- Review error messages and status codes
- Verify API key status in the management interface
