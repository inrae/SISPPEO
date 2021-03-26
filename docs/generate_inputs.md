## l3 algo

config keys :

    - input_product
    - product_type
    - fmt
    - glint_corrected
    - lst_algos
    - lst_band
    - lst_calib
    - code_site
    - out_resolution
    - geom
    - dirname  ||  filenames
    - lst_l3mask_path
    - lst_l3mask_type


## batch algo

config keys :

    - input_products
    - product_types
    - lst_fmt
    - lst_gc
    - lst_algos
    - lst_band
    - lst_calib
    - lst_code_site
    - lst_res
    - lst_geom
    - dirname  ||  filenames
    - lst_l3masks_paths
    - lst_l3masks_types
    - num_cpus


## time series

config keys :

    - input_products
    - product_types
    - lst_fmt
    - lst_gc
    - lst_algos
    - lst_code_site
    - lst_res
    - lst_geom
    - dirname  ||  filenames
    - lst_l3masks_paths
    - lst_l3masks_types
    - lst_tsmask_path
    - lst_tsmask_type
    - num_cpus


## l3 mask

config keys :

    - input_product
    - product_type
    - glint_corrected
    - lst_masks
    - code_site
    - out_resolution
    - processing_resolution
    - geom
    - dirname  ||  filenames


## batch mask

config keys :

    - input_products
    - product_types
    - lst_gc
    - lst_masks
    - lst_code_site
    - lst_res
    - lst_proc_res
    - lst_geom
    - dirname  ||  filenames
    - num_cpus


## time series (mask)

config keys :

    - input_products
    - product_types
    - glint_corrected
    - lst_masks
    - code_site
    - out_resolution
    - processing_resolution
    - geom
    - dirname  ||  filenames
    - num_cpus


## match up

config keys :

    - input_product
    - product_type
    - sat
    - fmt
    - glint_corrected
    - requested_bands
    - points
    - code_site
    - out_resolution
    - dirname  ||  filenames
    - lst_mask_path
    - lst_mask_type
