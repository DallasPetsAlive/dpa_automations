data "archive_file" "foster_agreement_webhook_zip" {
  type = "zip"

  source_dir  = "${path.module}/../foster_agreement_webhook"
  output_path = "${path.module}/foster_agreement_webhook.zip"
}

resource "aws_s3_object" "foster_agreement_object" {
  bucket = aws_s3_bucket.jotform_alerts_bucket.id

  key    = "foster_agreement_webhook.zip"
  source = data.archive_file.foster_agreement_webhook_zip.output_path

  etag = filemd5(data.archive_file.foster_agreement_webhook_zip.output_path)
}

resource "aws_lambda_function" "foster_agreement_webhook" {
  depends_on = [
    aws_cloudwatch_log_group.foster_agreement_webhook_log_group,
  ]

  function_name = "foster_agreement_webhook"
  role          = aws_iam_role.jotform_alerts_iam.arn
  handler       = "webhook.handler"

  s3_bucket = aws_s3_bucket.jotform_alerts_bucket.id
  s3_key    = aws_s3_object.foster_agreement_object.key

  source_code_hash = data.archive_file.foster_agreement_webhook_zip.output_base64sha256

  runtime = "python3.9"
  timeout = 60
}

resource "aws_lambda_permission" "allow_webhook_execution" {
  statement_id  = "AllowWebhookExecution"
  action        = "lambda:invokeFunctionUrl"
  function_name = aws_lambda_function.foster_agreement_webhook.function_name
  principal     = "*"
  function_url_auth_type = "NONE"
}

resource "aws_cloudwatch_log_group" "foster_agreement_webhook_log_group" {
  name              = "/aws/lambda/foster_agreement_webhook"
  retention_in_days = 90
}

resource "aws_lambda_function_url" "foster_agreement_webhook_url" {
  function_name      = aws_lambda_function.foster_agreement_webhook.function_name
  authorization_type = "NONE"
}

resource "aws_lambda_function_event_invoke_config" "foster_agreement_webhook_invoke_config" {
  function_name = aws_lambda_function.foster_agreement_webhook.function_name

  destination_config {
    on_failure {
      destination = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
    }
  }
}
