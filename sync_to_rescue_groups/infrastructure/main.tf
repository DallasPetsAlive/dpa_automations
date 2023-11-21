terraform {
  backend "s3" {
    bucket  = "dallas-pets-alive-terraform"
    key     = "new_digs_to_rescue_groups.tfstate"
    region  = "us-east-2"
  }

  required_providers {
    aws = {
      source = "hashicorp/aws"
      version = "4.40.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2.0"
    }
  }

  required_version = ">= 0.14.9"
}

provider "aws" {
  region  = "us-east-2"
}

data "archive_file" "sync_to_rescue_groups_zip" {
  type = "zip"

  source_dir  = "${path.module}/../sync_to_rescue_groups"
  output_path = "${path.module}/sync.zip"
}

resource "aws_s3_bucket" "sync_to_rescue_groups_bucket" {
  bucket = "dpa-rescue-groups-sync"
}

resource "aws_s3_object" "sync_to_rescue_groups_object" {
  bucket = aws_s3_bucket.sync_to_rescue_groups_bucket.id

  key    = "sync.zip"
  source = data.archive_file.sync_to_rescue_groups_zip.output_path

  etag = filemd5(data.archive_file.sync_to_rescue_groups_zip.output_path)
}

resource "aws_iam_role" "sync_to_rescue_groups_iam" {
  name = "sync_to_rescue_groups_iam"

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
    name = "sync_to_rescue_groups_iam_inline_policy"

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

resource "aws_lambda_function" "sync_to_rescue_groups" {
  depends_on = [
    aws_cloudwatch_log_group.sync_to_rescue_groups_log_group,
  ]

  function_name = "sync_to_rescue_groups"
  role          = aws_iam_role.sync_to_rescue_groups_iam.arn
  handler       = "sync_to_rescue_groups.handler"

  s3_bucket = aws_s3_bucket.sync_to_rescue_groups_bucket.id
  s3_key    = aws_s3_object.sync_to_rescue_groups_object.key

  source_code_hash = data.archive_file.sync_to_rescue_groups_zip.output_base64sha256

  runtime = "python3.9"
  timeout = 60

  layers = [aws_lambda_layer_version.sync_to_rescue_groups_layer.arn]
}

resource "aws_lambda_function_event_invoke_config" "sync_to_rescue_groups_invoke_config" {
  function_name = aws_lambda_function.sync_to_rescue_groups.function_name

  destination_config {
    on_failure {
      destination = "arn:aws:sns:us-east-2:832971646995:Default_CloudWatch_Alarms_Topic"
    }
  }
}

resource "null_resource" "layer_creation" {
  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {
   command = "mkdir -p ${path.module}/requests_layer/python && pip install requests==2.28.2 -t ${path.module}/requests_layer/python"
  }
}

data "archive_file" "requests_zip" {
  type = "zip"
  depends_on = [null_resource.layer_creation]

  source_dir  = "${path.module}/requests_layer"
  output_path = "${path.module}/requests.zip"
}

resource "aws_lambda_layer_version" "sync_to_rescue_groups_layer" {
  filename   = data.archive_file.requests_zip.output_path
  layer_name = "sync_to_rescue_groups_layer"
  source_code_hash = data.archive_file.requests_zip.output_base64sha256

  compatible_runtimes = ["python3.9"]
}

resource "aws_cloudwatch_log_group" "sync_to_rescue_groups_log_group" {
  name              = "/aws/lambda/sync_to_rescue_groups"
  retention_in_days = 90
}

resource "aws_iam_policy" "sync_to_rescue_groups_logging_policy" {
  name   = "sync_to_rescue_groups_logging_policy"
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

resource "aws_iam_role_policy_attachment" "sync_to_rescue_groups_logging_policy_attachment" {
  role = aws_iam_role.sync_to_rescue_groups_iam.id
  policy_arn = aws_iam_policy.sync_to_rescue_groups_logging_policy.arn
}

resource "aws_cloudwatch_event_rule" "sync_to_rescue_groups_event_rule" {
  name = "sync_to_rescue_groups_event_rule"
  description = "invoke rescuegroups sync once an hour"
  schedule_expression = "rate(1 hour)"
}

resource "aws_cloudwatch_event_target" "sync_to_rescue_groups_event_target" {
  arn = aws_lambda_function.sync_to_rescue_groups.arn
  rule = aws_cloudwatch_event_rule.sync_to_rescue_groups_event_rule.name
}

resource "aws_lambda_permission" "sync_to_rescue_groups_cloudwatch_permission" {
  statement_id = "AllowExecutionFromCloudWatch"
  action = "lambda:InvokeFunction"
  function_name = "sync_to_rescue_groups"
  principal = "events.amazonaws.com"
  source_arn = aws_cloudwatch_event_rule.sync_to_rescue_groups_event_rule.arn
}

data "aws_secretsmanager_secret" "shelterluv_api_key" {
  name = "shelterluv_api_key"
}

resource "aws_iam_policy" "rg_sync_get_shelterluv_api_key" {
  name = "rg_sync_get_shelterluv_api_key"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = [
        "secretsmanager:GetSecretValue",
      ]
      Effect = "Allow"
      Resource = [
        data.aws_secretsmanager_secret.shelterluv_api_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "secrets_lambda_policy" {
  role       = aws_iam_role.sync_to_rescue_groups_iam.name
  policy_arn = aws_iam_policy.rg_sync_get_shelterluv_api_key.arn
}
