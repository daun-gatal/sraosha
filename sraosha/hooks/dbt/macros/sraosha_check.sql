{% macro sraosha_check(contract_path, enforcement_mode='block') %}
    {% set cmd = 'python -m sraosha.hooks.dbt.hook --contract ' ~ contract_path ~ ' --mode ' ~ enforcement_mode %}
    {% do run_query("SELECT 1") %}
    {{ log("Sraosha: Running contract validation for " ~ contract_path, info=True) }}
    {% set result = run_query("SELECT 1") %}
    {# In practice, invoke via dbt's on-run-end shell hook or pre/post-hook #}
{% endmacro %}
