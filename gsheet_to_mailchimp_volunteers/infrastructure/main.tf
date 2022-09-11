terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "gsheet_to_mailchimp_volunteers.tfstate"
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
  profile = "default"
  region  = "us-east-2"
}

resource "aws_iam_role" "gsheet_to_mailchimp_volunteers_iam" {
  name = "gsheet_to_mailchimp_volunteers_iam"

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

  inline_policy {
    name = "gsheet_to_mailchimp_volunteers_iam_inline_policy"

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [
        {
          Action   = ["sns:Publish*"]
          Effect   = "Allow"
          Resource = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
        },
      ]
    })
  }
}

resource "aws_lambda_function" "gsheet_to_mailchimp_volunteers" {
  depends_on = [
    aws_cloudwatch_log_group.gsheet_to_mailchimp_volunteers_log_group,
  ]

  filename      = "gsheet_to_mailchimp_volunteers.zip"
  function_name = "gsheet_to_mailchimp_volunteers"
  role          = aws_iam_role.gsheet_to_mailchimp_volunteers_iam.arn
  handler       = "gsheet_to_mailchimp_volunteers.handler"

  source_code_hash = filebase64sha256("gsheet_to_mailchimp_volunteers.zip")

  runtime = "python3.9"
  timeout = 60

  layers = [aws_lambda_layer_version.gsheet_to_mailchimp_volunteers_layer.arn]
}

resource "aws_lambda_function_event_invoke_config" "gsheet_to_mailchimp_volunteers_invoke_config" {
  function_name = aws_lambda_function.gsheet_to_mailchimp_volunteers.function_name

  destination_config {
    on_failure {
      destination = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
    }
  }
}

resource "aws_lambda_layer_version" "gsheet_to_mailchimp_volunteers_layer" {
  filename   = "layer.zip"
  layer_name = "gsheet_to_mailchimp_volunteers_layer"

  compatible_runtimes = ["python3.9"]
}

resource "aws_cloudwatch_log_group" "gsheet_to_mailchimp_volunteers_log_group" {
  name              = "/aws/lambda/gsheet_to_mailchimp_volunteers"
  retention_in_days = 90
}

resource "aws_iam_policy" "gsheet_to_mailchimp_volunteers_logging_policy" {
  name   = "gsheet_to_mailchimp_volunteers_logging_policy"
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

resource "aws_iam_role_policy_attachment" "gsheet_to_mailchimp_volunteers_logging_policy_attachment" {
  role = aws_iam_role.gsheet_to_mailchimp_volunteers_iam.id
  policy_arn = aws_iam_policy.gsheet_to_mailchimp_volunteers_logging_policy.arn
}

resource "aws_cloudwatch_event_rule" "gsheet_to_mailchimp_volunteers_event_rule" {
  name = "gsheet_to_mailchimp_volunteers_event_rule"
  description = "invoke gsheet to mailchimp volunteer sync once a day"
  schedule_expression = "rate(1 day)"
}

resource "aws_cloudwatch_event_target" "gsheet_to_mailchimp_volunteers_event_target" {
  arn = aws_lambda_function.gsheet_to_mailchimp_volunteers.arn
  rule = aws_cloudwatch_event_rule.gsheet_to_mailchimp_volunteers_event_rule.name
}

resource "aws_lambda_permission" "gsheet_to_mailchimp_volunteers_cloudwatch_permission" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "gsheet_to_mailchimp_volunteers"
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.gsheet_to_mailchimp_volunteers_event_rule.arn
}
