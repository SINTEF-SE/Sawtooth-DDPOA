

trap ctrl_c INT

ctrl_c () {
    ./clear_tests.sh
    exit 148
}

./clear_tests.sh
docker compose --env-file ./testing/fault_tolerance/.env --file ./testing/test_crash_fault_tolerance.yml up --build --force-recreate

echo "Ctrl-c to stop the test"
while true; do
    sleep 1
done
