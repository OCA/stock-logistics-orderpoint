- There is a security group 'Location Orderpoint Cleanup Group'. Users
  that can have access to cleanup action should be in that group. By default,
  all users that are in 'Inventory/Administrator' are in that group.
- You can configure crons to execute cleanup actions.
  - Enable debug mode, go to Settings > Technical > Scheduled Actions
  - Add a cron with:
    - base model 'Stock Location Orderpoint'
    - In python code, add a line 'model.run_cleanup(orderpoints, run_after)' where 'orderpoints' is a list of orderpoint ids and 'run_after' is True if you want to run the orderpoint(s) after cleanup.
    - If you want to cleanup ordepoints by replenish method, add a line 'model.run_cleanup_method(replenish_method, run_after)' where 'replenish_method' is 'fill_up' by default (depending on extension modules you have installed)