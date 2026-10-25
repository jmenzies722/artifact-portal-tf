locals {
  # One Lambda per route. Keys match folder names under lambda/.
  functions = {
    list_files   = { route = "GET /files" }
    upload_url   = { route = "POST /upload" }
    download_url = { route = "GET /download" }
    delete_file  = { route = "DELETE /files" }
  }

  function_names = { for k in keys(local.functions) : k => "${var.name_prefix}-${replace(k, "_", "-")}" }

  lambda_src   = "${path.module}/../../lambda"
  shared_files = ["__init__.py", "permissions.py", "http.py"]
}

# Each zip = handler.py + shared/. Built from file contents, so no build step.
data "archive_file" "fn" {
  for_each    = local.functions
  type        = "zip"
  output_path = "${path.module}/.build/${each.key}.zip"

  source {
    content  = file("${local.lambda_src}/${each.key}/handler.py")
    filename = "handler.py"
  }

  dynamic "source" {
    for_each = local.shared_files
    content {
      content  = file("${local.lambda_src}/shared/${source.value}")
      filename = "shared/${source.value}"
    }
  }
}
