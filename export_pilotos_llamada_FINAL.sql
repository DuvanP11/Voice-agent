-- =====================================================
-- QUERY FINAL: LISTA DE PILOTOS PARA CAMPAÑA DE LLAMADAS
-- Basado en datos reales de ClickHouse
-- =====================================================

WITH rechazos_recientes AS (
    -- Documentos rechazados en los últimos 14 días
    SELECT 
        defs.passenger_id,
        defs.driver_enrollment_document_form_id,
        dedf.form_key,
        defs.status_cd,
        defs.rejected_reason_id,
        defs.comment,
        defs.created_at,
        defs.updated_at,
        -- Contar intentos por documento
        ROW_NUMBER() OVER (
            PARTITION BY defs.passenger_id, defs.driver_enrollment_document_form_id 
            ORDER BY defs.created_at DESC
        ) as intento_numero
    FROM picapmongoprod.driver_enrollment_document_form_solutions defs
    LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
        ON defs.driver_enrollment_document_form_id = dedf._id
    WHERE defs.status_cd = 3  -- 3 = Rechazado
    AND defs.created_at >= now() - INTERVAL 14 DAY
),

stats_por_piloto AS (
    -- Agrupar rechazos por piloto
    SELECT 
        passenger_id,
        COUNT(DISTINCT driver_enrollment_document_form_id) as documentos_diferentes_rechazados,
        COUNT(*) as total_intentos_rechazados,
        MAX(updated_at) as fecha_ultimo_rechazo,
        groupArray(form_key) as form_keys_rechazados,
        groupArray(comment) as comentarios_rechazo
    FROM rechazos_recientes
    GROUP BY passenger_id
    HAVING documentos_diferentes_rechazados >= 2  -- Al menos 2 documentos rechazados
),

info_completa_piloto AS (
    SELECT 
        p._id as passenger_id,
        p.name as nombre_completo,
        pwd.txt_phone as telefono,
        pwd.txt_full_phone as telefono_completo,
        p.country_code_phone as codigo_pais,
        pwd.txt_email as email,
        pwd.cod_identification as cedula,
        p.driver_enrollment_status_cd as status_enrollment,
        p.created_at as fecha_registro,
        p.is_activated,
        -- Detectar país
        CASE 
            WHEN p.country_code_phone = '57' THEN 'CO'
            WHEN p.country_code_phone = '52' THEN 'MX'
            WHEN p.country_code_phone = '54' THEN 'AR'
            WHEN p.country_code_phone = '593' THEN 'EC'
            WHEN p.country_code_phone = '502' THEN 'GT'
            WHEN p.country_code_phone = '505' THEN 'NI'
            WHEN p.country_code_phone = '58' THEN 'VE'
            ELSE 'OTHER'
        END as pais
    FROM picapmongoprod.passengers p
    LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
    WHERE p.driver_enrollment_status_cd IN (0, 2)  -- 0=Pendiente, 2=En Revisión
    AND p.is_activated = 0  -- No activado
)

-- RESULTADO FINAL
SELECT 
    icp.passenger_id,
    icp.nombre_completo,
    icp.telefono,
    icp.codigo_pais,
    icp.pais,
    icp.email,
    icp.cedula,
    icp.status_enrollment,
    toDate(icp.fecha_registro) as fecha_registro,
    -- Métricas de rechazo
    spp.documentos_diferentes_rechazados,
    spp.total_intentos_rechazados,
    toDate(spp.fecha_ultimo_rechazo) as fecha_ultimo_rechazo,
    dateDiff('day', spp.fecha_ultimo_rechazo, now()) as dias_desde_ultimo_rechazo,
    -- Documentos rechazados
    arrayStringConcat(spp.form_keys_rechazados, ', ') as documentos_rechazados,
    -- Prioridad
    CASE 
        WHEN spp.total_intentos_rechazados >= 5 THEN 'ALTA'
        WHEN spp.total_intentos_rechazados >= 3 THEN 'MEDIA'
        ELSE 'BAJA'
    END as prioridad_llamada,
    -- Número formateado para Twilio
    concat('+', icp.codigo_pais, icp.telefono) as numero_twilio
FROM info_completa_piloto icp
INNER JOIN stats_por_piloto spp ON icp.passenger_id = spp.passenger_id
WHERE 
    -- Filtros de calidad de datos
    icp.telefono IS NOT NULL
    AND length(icp.telefono) >= 10
    AND icp.pais != 'OTHER'  -- Solo países soportados
    -- Excluir test
    AND icp.nombre_completo NOT LIKE '%test%'
    AND icp.nombre_completo NOT LIKE '%prueba%'
ORDER BY 
    prioridad_llamada DESC,
    spp.total_intentos_rechazados DESC,
    spp.fecha_ultimo_rechazo DESC
LIMIT 1000
FORMAT CSVWithNames;


-- =====================================================
-- QUERY ALTERNATIVO: Solo Colombia (para pruebas)
-- =====================================================

-- Descomentar para usar solo Colombia
/*
SELECT 
    icp.passenger_id,
    icp.nombre_completo,
    icp.telefono,
    icp.codigo_pais,
    icp.email,
    spp.documentos_diferentes_rechazados,
    spp.total_intentos_rechazados,
    concat('+', icp.codigo_pais, icp.telefono) as numero_twilio
FROM info_completa_piloto icp
INNER JOIN stats_por_piloto spp ON icp.passenger_id = spp.passenger_id
WHERE 
    icp.telefono IS NOT NULL
    AND icp.pais = 'CO'  -- Solo Colombia
    AND icp.codigo_pais = '57'
ORDER BY spp.total_intentos_rechazados DESC
LIMIT 100
FORMAT CSVWithNames;
*/
