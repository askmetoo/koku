# Generated by Django 2.2.9 on 2020-02-03 17:58
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [("reporting", "0091_aws_compute_cost_correction")]

    operations = [
        migrations.RunSQL(
            """
            DROP MATERIALIZED VIEW IF EXISTS reporting_aws_compute_summary_by_account;

            CREATE MATERIALIZED VIEW reporting_aws_compute_summary_by_account AS (
            SELECT row_number() OVER (order by c.usage_start, c.usage_account_id, c.account_alias_id, c.instance_type) as id,
                c.usage_start,
                c.usage_start as usage_end,
                c.usage_account_id,
                c.account_alias_id,
                c.instance_type,
                r.resource_ids,
                cardinality(r.resource_ids) as resource_count,
                c.usage_amount,
                c.unit,
                c.unblended_cost,
                c.markup_cost,
                c.currency_code
            FROM (
                    -- this group by gets the counts
                    SELECT date(usage_start) as usage_start,
                        usage_account_id,
                        account_alias_id,
                        instance_type,
                        sum(usage_amount) as usage_amount,
                        max(unit) as unit,
                        sum(unblended_cost) as unblended_cost,
                        sum(markup_cost) as markup_cost,
                        max(currency_code) as currency_code
                    FROM reporting_awscostentrylineitem_daily_summary
                    WHERE usage_start >= date_trunc('month', now() - '1 month'::interval)
                        AND usage_start < date_trunc('month', now() + '1 month'::interval)
                        AND instance_type is not null
                    GROUP BY date(usage_start),
                        usage_account_id,
                        account_alias_id,
                        instance_type
                ) AS c
            JOIN (
                    -- this group by gets the distinct resources running by day
                    SELECT usage_start,
                            usage_account_id,
                            account_alias_id,
                            instance_type,
                            array_agg(distinct resource_id order by resource_id) as resource_ids
                    FROM (
                            SELECT date(usage_start) as usage_start,
                                    usage_account_id,
                                    account_alias_id,
                                    instance_type,
                                    unnest(resource_ids) as resource_id
                                from reporting_awscostentrylineitem_daily_summary
                            where usage_start >= date_trunc('month', now() - '1 month'::interval)
                                and usage_start < date_trunc('month', now() + '1 month'::interval)
                                and instance_type is not null
                            ) as x
                    GROUP BY date(usage_start),
                        usage_account_id,
                        account_alias_id,
                        instance_type
                ) AS r
                ON c.usage_start = r.usage_start
                    AND (
                            (c.usage_account_id = r.usage_account_id)
                            OR (c.account_alias_id = r.account_alias_id)
                        )
                    AND c.instance_type = r.instance_type
                )
            WITH data
                ;


            CREATE UNIQUE INDEX aws_compute_summary_account
                ON reporting_aws_compute_summary_by_account (usage_start, usage_account_id, account_alias_id, instance_type)
            ;
            """
        )
    ]
