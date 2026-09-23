resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/afterhourz-${var.env}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "main" {
  name = "afterhourz-${var.env}"
  setting {
    name  = "containerInsights"
    value = "disabled" # paid feature; enable for prod once you want the dashboards
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
}

resource "aws_ecs_task_definition" "api" {
  family                   = "afterhourz-${var.env}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  # X86_64 keeps CI simple (GitHub's default runners are x86). Graviton (ARM64) is ~20%
  # cheaper: switch this AND build the image for linux/arm64 to take it.
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name         = "api"
    image        = var.image
    essential    = true
    portMappings = [{ containerPort = 8000, protocol = "tcp" }]

    environment = [
      { name = "ENV", value = var.env },
      { name = "AWS_REGION", value = var.region },
      { name = "TABLE_NAME", value = var.table_name },
      { name = "FRONTEND_ORIGIN", value = var.site_url },
      { name = "GOOGLE_CLIENT_ID", value = var.google_client_id },
      { name = "ADMIN_EMAILS", value = var.admin_emails },
      { name = "SES_FROM", value = var.ses_from },
      { name = "SMS_ENABLED", value = tostring(var.sms_enabled) },
      { name = "PAYMENTS_ENABLED", value = tostring(var.payments_enabled) },
      { name = "GOOGLE_CALENDAR_ID", value = var.google_calendar_id },
    ]

    # "<secret-arn>:<json-key>::" makes ECS inject a single key of the JSON secret.
    secrets = [
      { name = "JWT_SECRET", valueFrom = "${var.secret_arn}:JWT_SECRET::" },
      { name = "STRIPE_SECRET_KEY", valueFrom = "${var.secret_arn}:STRIPE_SECRET_KEY::" },
      { name = "STRIPE_WEBHOOK_SECRET", valueFrom = "${var.secret_arn}:STRIPE_WEBHOOK_SECRET::" },
      { name = "GOOGLE_SERVICE_ACCOUNT_JSON", valueFrom = "${var.secret_arn}:GOOGLE_SERVICE_ACCOUNT_JSON::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "api"
      }
    }
  }])
}

resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.desired_count
  propagate_tags  = "SERVICE"

  # Dev runs on Spot (~70% cheaper; an interruption just restarts the task). Prod is on-demand.
  capacity_provider_strategy {
    capacity_provider = var.use_spot ? "FARGATE_SPOT" : "FARGATE"
    weight            = 1
  }

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  # Rolling deploy with automatic rollback: if new tasks never turn healthy, ECS keeps the old
  # ones serving and reverts. `terraform apply` waits for that verdict and fails loudly.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200
  health_check_grace_period_seconds  = 30
  wait_for_steady_state              = true

  depends_on = [aws_lb_listener_rule.from_cloudfront, aws_ecs_cluster_capacity_providers.main]
}
