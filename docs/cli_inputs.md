## create\_l3algo

Args:

    - input_product : 1
    - product_type : 1
    - fmt : *1*
    - *glint_corrected*
    - algo : 1 ou plrs                 ||  algos_list
    - algo_band : *1 ou plrs*          ||
    - algo_calib : *1 ou plrs*         ||
    - algo_custom_calib : *1 ou plrs*  ||
    - output_dir : 1  || out_products : 1 ou plrs
    - mask_path : *1 ou plrs*  \\ masks_list
    - mask_type : *1 ou plrs*  ||
    - wkt : *1*
    - shp : *1*
    - wkt_file : *1*
    - srid : *1*
    - code_site : *1*
    - res : *1*


## create\_batch\_l3algo

Args:

    - input_product : 1 ou plrs      ||  products_list : 1
    - product_type : 1 ou plrs       ||
    - fmt : *1 ou plrs*              ||
    - glint_corrected : *1 ou plrs*  ||
    - masks_list : *1 ou plrs*       ||
    - wkt : *1*                      ||
    - shp : *1*                      ||
    - wkt_file : *1*                 ||
    - srid : *1*                     ||
    - code_site : *1*                ||
    - res : *1*                      ||
    - algo : 1 ou plrs                 ||  algos_list
    - algo_band : *1 ou plrs*          ||
    - algo_calib : *1 ou plrs*         ||
    - algo_custom_calib : *1 ou plrs*  ||
    - num_cpus : *1*
    - output_dir : 1  ||  out_product : 1 ou plrs  ||  products_list : 1

products\_list: text file with the following collumns : input\_product, product\_type *, fmt, glint\_corrected, masks\_list, wkt, shp, wkt\_file, srid, code\_site, res*.  
separator = ' '

masks\_list: text file with the following collumns : mask\_path, mask\_type  
separator = ' '


## create_timeseries

Args:

    - input_product : 1 ou plrs      ||  products_list : 1
    - masks_list : *1 ou plrs*       ||
    - fmt : *1*
    - product_type : 1
    - *glint_corrected*
    - algo : 1 ou plrs
    - num_cpus : *1*
    - output_dir : 1  || out_products : 1 ou plrs
    - tsmask_path : *1 ou plrs*
    - tsmask_type : *1 ou plrs*
    - wkt : *1*
    - shp : *1*
    - wkt_file : *1*
    - srid : *1*
    - code_site : *1*
    - res : *1*

product\_list: text file with the following collumns : input\_product *, fmt, masks\_list*  (one can reuse file for "create\_batch\_l3masks" ; suppl. columns will be ignored)  
separator = ' '

masks\_list: text file with the following collumns : mask\_path, mask\_type  
separator = ' '


## create_l3mask

Args:

    - input_product : 1
    - product_type : 1
    - *glint_corrected*
    - mask : 1 ou plrs
    - output_dir : 1  ||  out_products : 1 ou plrs
    - wkt : *1*
    - shp : *1*
    - wkt_file : *1*
    - srid : *1*
    - code_site : *1*
    - res : *1*
    - proc_res : *1*


## create_batch_l3mask

Args:

    - input_product : 1 ou plrs      ||  products_list : 1
    - product_type : 1 ou plrs       ||
    - glint_corrected : *1*          ||
    - wkt : *1*                      ||
    - shp : *1*                      ||
    - wkt_file : *1*                 ||
    - srid : *1*                     ||
    - code_site : *1*                ||
    - res : *1*                      ||
    - proc_res : *1*                 ||
    - mask : 1 ou plrs
    - num_cpus : *1*
    - output_dir : 1  ||  out_products : 1 ou plrs  ||  products_list : 1

product\_list: text file with the following collumns : input\_product, product\_type *, glint\_corrected, wkt, shp, wkt\_file, srid, code\_site, res, proc_res*.  
separator = ' '


## create_timeseries_mask

Args:

    - input_product : 1 ou plrs      ||  products_list : 1
    - product_type : 1
    - *glint_corrected*
    - mask : 1 ou plrs
    - num_cpus : *1*
    - output_dir : 1  || out_products : 1 ou plrs
    - wkt : *1*
    - shp : *1*
    - wkt_file : *1*
    - srid : *1*
    - code_site : *1*
    - res : *1*
    - proc_res : *1*

product\_list: text file with the following collumns : input\_product  (one can reuse file for "create\_batch\_l3masks" ; suppl. columns will be ignored)  
separator = ' '

    
## create_matchup

Args:

    - input_product : 1
    - product_type : 1
    - sat : 1 (temporaire)
    - fmt : *1*
    - *glint_corrected*
    - requested_band : 1 ou plrs
    - (flag "all_bands")
    - points
    - output_dir : 1  || out_product : 1
    - mask_path : *1 ou plrs*  ||  masks_list
    - mask_type : *1 ou plrs*  ||
    - code_site : *1*
    - res: *1*


\*arg\* are optional arguments
