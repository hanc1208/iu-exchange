aws ecs list-tasks --cluster iu-exchange | \
python -c "import json,sys;obj=json.load(sys.stdin);[print(arn) for arn in obj['taskArns']]" | \
xargs -L1 aws ecs stop-task --cluster iu-exchange --task
