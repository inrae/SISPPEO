import sisppeo
from pathlib import Path
import yaml
import sys 

if __name__ == '__main__':
    

    if(len(sys.argv)>1):
        config_file=sys.argv[1]
    else:
        config_file="/data/config.yml"

    with open(config_file, 'r') as yamlfile:
        data = yaml.load(yamlfile, Loader=yaml.FullLoader)


    config = {
        'input_product' : data["input_product"], #'/work/ALT/swot/aval/OBS2CO/Input_WaterDetect/Input_France/2019-06/T31TFJ/SENTINEL2B_20190604-103902-224_L2A_T31TFJ_C_V2-2',
        'product_type': data["product_type"], # 'S2_THEIA',

    }

    for key, value in data.items():
        if(value is not None and value!=''):
            config[key]=value

    print(config)
    result_list = sisppeo.generate(data["algorithm"], config, save=True)



