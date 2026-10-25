resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"

  # Preflight (OPTIONS) is answered by API Gateway itself, before the authorizer.
  cors_configuration {
    allow_origins = var.cors_origins
    allow_methods = ["GET", "POST", "DELETE"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age       = 300
  }
}

# Cognito access tokens carry client_id rather than aud; the HTTP API JWT
# authorizer checks client_id against audience for those, so client ids work.
resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = var.issuer_url
    audience = var.audiences
  }
}

resource "aws_apigatewayv2_integration" "fn" {
  for_each               = local.functions
  api_id                 = aws_apigatewayv2_api.this.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.fn[each.key].invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "fn" {
  for_each           = local.functions
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = each.value.route
  target             = "integrations/${aws_apigatewayv2_integration.fn[each.key].id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

# Each function may be invoked only by its own route, e.g. .../*/GET/files.
resource "aws_lambda_permission" "apigw" {
  for_each      = local.functions
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.fn[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.this.execution_arn}/*/${replace(each.value.route, " ", "")}"
}
