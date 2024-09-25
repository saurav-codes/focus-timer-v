# reset all the logs in logs/

echo "Resetting all the logs in logs/"
echo "" > ./logs/django.log
echo "" > ./logs/nginx-access.log
echo "" > ./logs/nginx-error.log
echo "" > ./logs/redis_scheduler.log
echo "✨ All logs have been successfully cleared! ✨"
