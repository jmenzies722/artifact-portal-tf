output "api_url" {
  value = aws_apigatewayv2_api.this.api_endpoint
}

output "api_id" {
  value = aws_apigatewayv2_api.this.id
}

output "audit_table_name" {
  value = aws_dynamodb_table.audit.name
}

output "function_names" {
  value = { for k, fn in aws_lambda_function.fn : k => fn.function_name }
}
