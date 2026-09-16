UPDATE settings
   SET setting_value = CASE
         WHEN setting_value = 'Retailer'  THEN 'Retail'
         WHEN setting_value = 'Wholesaler' THEN 'Wholesale'
         ELSE setting_value
       END,
       updated_at = CURRENT_TIMESTAMP,
       updated_by = 'normalization-migration'
 WHERE setting_key = 'general.business_type'
   AND setting_value IN ('Retailer', 'Wholesaler');