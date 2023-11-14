terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "wordpress_pet_sync.tfstate"
    region  = "us-east-2"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 3.27"
    }
  }

  required_version = ">= 0.14.9"
}

provider "aws" {
  region  = "us-east-2"
}

data "archive_file" "lambda_wordpress_pet_sync" {
  type = "zip"

  source_dir  = "${path.module}/../wordpress_pet_sync/"
  output_path = "${path.module}/wordpress_pet_sync.zip"
}

resource "aws_iam_role" "wordpress_pet_sync_iam" {
  name = "wordpress_pet_sync_iam"

  assume_role_policy = jsonencode({
    "Version": "2012-10-17",
    "Statement": [
      {
        "Action": "sts:AssumeRole",
        "Principal": {
          "Service": "lambda.amazonaws.com"
        },
        "Effect": "Allow",
        "Sid": ""
      }
    ]
  })
}

resource "aws_lambda_function" "wordpress_pet_sync" {
  depends_on = [
    aws_cloudwatch_log_group.wordpress_pet_sync_log_group,
  ]

  filename      = "wordpress_pet_sync.zip"
  function_name = "wordpress_pet_sync"
  role          = aws_iam_role.wordpress_pet_sync_iam.arn
  handler       = "wordpress_pet_sync.handler"
  timeout       = 300

  source_code_hash = filebase64sha256(data.archive_file.lambda_wordpress_pet_sync.output_path)

  runtime = "python3.9"

  layers = [data.aws_lambda_layer_version.requests_layer.arn, data.aws_lambda_layer_version.api_layer.arn]
}

data "aws_lambda_layer_version" "requests_layer" {
  layer_name = "requests_layer"
}

data "aws_lambda_layer_version" "api_layer" {
  layer_name = "api_layer"
}

resource "aws_cloudwatch_log_group" "wordpress_pet_sync_log_group" {
  name              = "/aws/lambda/wordpress_pet_sync"
  retention_in_days = 90
}

resource "aws_iam_policy" "wordpress_pet_sync_logging_policy" {
  name   = "wordpress_pet_sync_logging_policy"
  policy = jsonencode({
    "Version" : "2012-10-17",
    "Statement" : [
      {
        Action : [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect : "Allow",
        Resource : "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "wordpress_pet_sync_logging_policy_attachment" {
  role = aws_iam_role.wordpress_pet_sync_iam.id
  policy_arn = aws_iam_policy.wordpress_pet_sync_logging_policy.arn
}

resource "aws_cloudwatch_event_rule" "wordpress_pet_sync_event_rule" {
  name = "wordpress_pet_sync_event_rule"
  description = "invoke wordpress pet sync once an hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "wordpress_pet_sync_event_target" {
  arn = aws_lambda_function.wordpress_pet_sync.arn
  rule = aws_cloudwatch_event_rule.wordpress_pet_sync_event_rule.name
}

resource "aws_lambda_permission" "wordpress_pet_sync_cloudwatch_permission" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "wordpress_pet_sync"
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.wordpress_pet_sync_event_rule.arn
}

data "aws_secretsmanager_secret" "wordpress_credentials" {
  name = "wordpress_credentials"
}

resource "aws_iam_policy" "wordpress_sync_get_wordpress_credentials" {
  name = "wordpress_sync_get_wordpress_credentials"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Effect = "Allow"
      Resource = [
        data.aws_secretsmanager_secret.wordpress_credentials.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_lambda_policy" {
  role       = aws_iam_role.wordpress_pet_sync_iam.name
  policy_arn = aws_iam_policy.wordpress_sync_get_wordpress_credentials.arn
}

data "aws_secretsmanager_secret" "slack_alerts_webhook" {
  name = "slack_alerts_webhook"
}

resource "aws_iam_policy" "wordpress_sync_get_slack_alerts_webhook" {
  name = "wordpress_sync_get_slack_alerts_webhook"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Effect = "Allow"
      Resource = [
        data.aws_secretsmanager_secret.slack_alerts_webhook.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_lambda_policy_slack" {
  role       = aws_iam_role.wordpress_pet_sync_iam.name
  policy_arn = aws_iam_policy.wordpress_sync_get_slack_alerts_webhook.arn
}

data "aws_dynamodb_table" "pets-table" {
  name = "Pets"
}

resource "aws_iam_policy" "wordpress_dynamodb_pets_get_list" {
  name = "wordpress_dynamodb_pets_get_list"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:Scan",
        "dynamodb:BatchWriteItem",
        "dynamodb:PutItem",
      ]
      Effect = "Allow"
      Resource = [
        data.aws_dynamodb_table.pets-table.arn,
        "${data.aws_dynamodb_table.pets-table.arn}/index/*",
        aws_dynamodb_table.featured-photos.arn,
        "${aws_dynamodb_table.featured-photos.arn}/index/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dynamodb_lambda_policy" {
  role       = aws_iam_role.wordpress_pet_sync_iam.name
  policy_arn = aws_iam_policy.wordpress_dynamodb_pets_get_list.arn
}
