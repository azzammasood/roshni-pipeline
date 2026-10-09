{% test accepted_range(model, column_name, min_value=none, max_value=none) %}
-- Rows where the column falls outside [min_value, max_value] (nulls are ignored).
select *
from {{ model }}
where {{ column_name }} is not null
  and (
    {% if min_value is not none %} {{ column_name }} < {{ min_value }} {% else %} 1 = 0 {% endif %}
    or
    {% if max_value is not none %} {{ column_name }} > {{ max_value }} {% else %} 1 = 0 {% endif %}
  )
{% endtest %}
