-- =====================================================
-- QUERY MAESTRO: IDENTIFICAR PILOTOS PARA LLAMADA
-- =====================================================
-- Encuentra pilotos con documentos rechazados que necesitan
-- orientación del agente de voz para corregir errores
-- =====================================================

WITH rechazos_documentos AS (
    -- Paso 1: Identificar documentos rechazados por piloto
    SELECT 
        defs.passenger_id,
        defs.driver_enrollment_document_form_id,
        dedf.form_key as tipo_documento,
        defs.status_cd,
        defs.rejected_reason_id,
        defs.comment as comentario_rechazo,
        defs.created_at as fecha_subida,
        defs.updated_at as fecha_actualizacion,
        -- Flags especiales SOAT y Tecnomecánica
        defs.should_reject_soat_form,
        defs.should_reject_tecno_form,
        defs.soat_expiration_date,
        defs.tecnomecanica_expiration_date,
        -- Contar intentos
        ROW_NUMBER() OVER (
            PARTITION BY defs.passenger_id, defs.driver_enrollment_document_form_id 
            ORDER BY defs.created_at DESC
        ) as intento_numero
    FROM picapmongoprod.driver_enrollment_document_form_solutions defs
    LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
        ON defs.driver_enrollment_document_form_id = dedf._id
    WHERE defs.status_cd = 3  -- 3 = Rechazado (confirmado)
    AND defs.created_at >= now() - INTERVAL 14 DAY  -- Últimos 14 días
),

pilotos_con_rechazos AS (
    -- Paso 2: Agrupar rechazos por piloto
    SELECT 
        passenger_id,
        COUNT(DISTINCT driver_enrollment_document_form_id) as documentos_rechazados,
        COUNT(*) as total_rechazos,
        MAX(fecha_actualizacion) as ultimo_rechazo,
        groupArray(tipo_documento) as docs_rechazados_list,
        groupArray(comentario_rechazo) as comentarios_list,
        -- Detectar si tiene problemas con SOAT/Tecno
        SUM(CASE WHEN should_reject_soat_form = 1 THEN 1 ELSE 0 END) as rechazos_soat_auto,
        SUM(CASE WHEN should_reject_tecno_form = 1 THEN 1 ELSE 0 END) as rechazos_tecno_auto
    FROM rechazos_documentos
    GROUP BY passenger_id
    HAVING documentos_rechazados >= 2  -- Al menos 2 documentos diferentes rechazados
),

info_piloto AS (
    -- Paso 3: Obtener información del piloto
    SELECT 
        p._id as passenger_id,
        pwd.cod_identification,
        p.name as nombre_piloto,
        pwd.txt_phone as telefono,
        pwd.txt_full_phone as telefono_completo,
        p.country_code_phone as codigo_pais,
        pwd.txt_email as email,
        p.driver_enrollment_status_cd as status_enrollment,
        p.created_at as fecha_registro,
        p.enrollment_approval_at as fecha_aprobacion,
        p.is_activated,
        p.driver_active_status_cd,
        -- Detectar país
        CASE 
            WHEN p.country_code_phone = '57' THEN 'CO'
            WHEN p.country_code_phone = '52' THEN 'MX'
            WHEN p.country_code_phone = '54' THEN 'AR'
            WHEN p.country_code_phone = '593' THEN 'EC'
            WHEN p.country_code_phone = '502' THEN 'GT'
            WHEN p.country_code_phone = '505' THEN 'NI'
            WHEN p.country_code_phone = '58' THEN 'VE'
            ELSE 'UNKNOWN'
        END as pais
    FROM picapmongoprod.passengers p
    LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
    WHERE p.driver_enrollment_status_cd IN (1, 2, 3)  -- AJUSTAR: Estados pendientes
)

-- Paso 4: RESULTADO FINAL - Lista de pilotos a llamar
SELECT 
    ip.passenger_id,
    ip.nombre_piloto,
    ip.telefono,
    ip.telefono_completo,
    ip.codigo_pais,
    ip.pais,
    ip.email,
    ip.cod_identification,
    ip.status_enrollment,
    ip.fecha_registro,
    -- Métricas de rechazo
    pcr.documentos_rechazados,
    pcr.total_rechazos,
    pcr.ultimo_rechazo,
    pcr.docs_rechazados_list,
    pcr.comentarios_list,
    pcr.rechazos_soat_auto,
    pcr.rechazos_tecno_auto,
    -- Días desde último rechazo
    dateDiff('day', pcr.ultimo_rechazo, now()) as dias_desde_ultimo_rechazo,
    -- Prioridad (más rechazos = más urgente)
    CASE 
        WHEN pcr.total_rechazos >= 5 THEN 'ALTA'
        WHEN pcr.total_rechazos >= 3 THEN 'MEDIA'
        ELSE 'BAJA'
    END as prioridad,
    -- Construir número telefónico completo para Twilio
    concat('+', ip.codigo_pais, ip.telefono) as numero_twilio
FROM info_piloto ip
INNER JOIN pilotos_con_rechazos pcr ON ip.passenger_id = pcr.passenger_id
WHERE 
    -- Filtros de calidad
    ip.telefono IS NOT NULL
    AND length(ip.telefono) >= 10
    AND ip.is_activated = 0  -- No está activado aún
    -- Excluir pilotos ya contactados (agregar JOIN con tabla de llamadas cuando exista)
    -- AND NOT EXISTS (SELECT 1 FROM voice_calls WHERE pilot_id = ip.passenger_id)
ORDER BY 
    prioridad DESC,
    pcr.total_rechazos DESC,
    pcr.ultimo_rechazo DESC
LIMIT 1000;


-- =====================================================
-- QUERIES DE SOPORTE ADICIONALES
-- =====================================================

-- Query 2: Análisis de razones de rechazo más comunes
-- =====================================================
SELECT 
    dedf.form_key as tipo_documento,
    defs.rejected_reason_id,
    defs.comment,
    COUNT(*) as cantidad_rechazos,
    COUNT(DISTINCT defs.passenger_id) as pilotos_afectados
FROM picapmongoprod.driver_enrollment_document_form_solutions defs
LEFT JOIN picapmongoprod.driver_enrollment_document_forms dedf 
    ON defs.driver_enrollment_document_form_id = dedf._id
WHERE defs.status_cd = 3  -- Rechazado
AND defs.created_at >= now() - INTERVAL 30 DAY
GROUP BY tipo_documento, rejected_reason_id, comment
ORDER BY cantidad_rechazos DESC
LIMIT 50;


-- Query 3: Pilotos con rechazos automáticos SOAT/Tecnomecánica
-- =====================================================
SELECT 
    p.name as nombre_piloto,
    pwd.txt_phone as telefono,
    defs.should_reject_soat_form,
    defs.should_reject_tecno_form,
    defs.soat_expiration_date,
    defs.tecnomecanica_expiration_date,
    defs.runt_mssg as mensaje_runt,
    defs.comment
FROM picapmongoprod.driver_enrollment_document_form_solutions defs
JOIN picapmongoprod.passengers p ON defs.passenger_id = p._id
LEFT JOIN picapmongoprod.passengers_w_data pwd ON p._id = pwd._id
WHERE (defs.should_reject_soat_form = 1 OR defs.should_reject_tecno_form = 1)
AND defs.created_at >= now() - INTERVAL 7 DAY
ORDER BY defs.created_at DESC
LIMIT 100;


-- Query 4: Dashboard de métricas de rechazo por país
-- =====================================================
WITH rechazos_por_pais AS (
    SELECT 
        CASE 
            WHEN p.country_code_phone = '57' THEN 'Colombia'
            WHEN p.country_code_phone = '52' THEN 'México'
            WHEN p.country_code_phone = '54' THEN 'Argentina'
            WHEN p.country_code_phone = '593' THEN 'Ecuador'
            WHEN p.country_code_phone = '502' THEN 'Guatemala'
            WHEN p.country_code_phone = '505' THEN 'Nicaragua'
            WHEN p.country_code_phone = '58' THEN 'Venezuela'
            ELSE 'Otro'
        END as pais,
        COUNT(*) as total_rechazos,
        COUNT(DISTINCT defs.passenger_id) as pilotos_afectados,
        AVG(dateDiff('day', p.created_at, defs.created_at)) as dias_promedio_hasta_rechazo
    FROM picapmongoprod.driver_enrollment_document_form_solutions defs
    JOIN picapmongoprod.passengers p ON defs.passenger_id = p._id
    WHERE defs.status_cd = 3
    AND defs.created_at >= now() - INTERVAL 30 DAY
    GROUP BY pais
)
SELECT 
    pais,
    total_rechazos,
    pilotos_afectados,
    round(dias_promedio_hasta_rechazo, 2) as dias_avg_rechazo,
    round(total_rechazos * 1.0 / pilotos_afectados, 2) as rechazos_por_piloto
FROM rechazos_por_pais
ORDER BY total_rechazos DESC;
