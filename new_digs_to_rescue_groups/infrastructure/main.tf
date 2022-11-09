terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "new_digs_to_rescue_groups.tfstate"
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
  profile = "dpa"
  region  = "us-east-2"
}

resource "aws_iam_role" "new_digs_to_rescue_groups_iam" {
  name = "new_digs_to_rescue_groups_iam"

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
    name = "new_digs_to_rescue_groups_iam_inline_policy"

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

resource "aws_lambda_function" "new_digs_to_rescue_groups" {
  depends_on = [
    aws_cloudwatch_log_group.new_digs_to_rescue_groups_log_group,
  ]

  filename      = "new_digs_to_rescue_groups.zip"
  function_name = "new_digs_to_rescue_groups"
  role          = aws_iam_role.new_digs_to_rescue_groups_iam.arn
  handler       = "new_digs_to_rescue_groups.handler"

  source_code_hash = filebase64sha256("new_digs_to_rescue_groups.zip")

  runtime = "python3.9"
  timeout = 60

  layers = [aws_lambda_layer_version.new_digs_to_rescue_groups_layer.arn]
}

resource "aws_lambda_function_event_invoke_config" "new_digs_to_rescue_groups_invoke_config" {
  function_name = aws_lambda_function.new_digs_to_rescue_groups.function_name

  destination_config {
    on_failure {
      destination = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
    }
  }
}

resource "aws_lambda_layer_version" "new_digs_to_rescue_groups_layer" {
  filename   = "requests.zip"
  layer_name = "new_digs_to_rescue_groups_layer"

  compatible_runtimes = ["python3.9"]
}

resource "aws_cloudwatch_log_group" "new_digs_to_rescue_groups_log_group" {
  name              = "/aws/lambda/new_digs_to_rescue_groups"
  retention_in_days = 90
}

resource "aws_iam_policy" "new_digs_to_rescue_groups_logging_policy" {
  name   = "new_digs_to_rescue_groups_logging_policy"
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

resource "aws_iam_role_policy_attachment" "new_digs_to_rescue_groups_logging_policy_attachment" {
  role = aws_iam_role.new_digs_to_rescue_groups_iam.id
  policy_arn = aws_iam_policy.new_digs_to_rescue_groups_logging_policy.arn
}

resource "aws_cloudwatch_event_rule" "new_digs_to_rescue_groups_event_rule" {
  name = "new_digs_to_rescue_groups_event_rule"
  description = "invoke new digs actions once an hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "new_digs_to_rescue_groups_event_target" {
  arn = aws_lambda_function.new_digs_to_rescue_groups.arn
  rule = aws_cloudwatch_event_rule.new_digs_to_rescue_groups_event_rule.name
}

resource "aws_lambda_permission" "new_digs_to_rescue_groups_cloudwatch_permission" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "new_digs_to_rescue_groups"
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.new_digs_to_rescue_groups_event_rule.arn
}
