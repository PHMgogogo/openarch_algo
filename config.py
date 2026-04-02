from os.path import abspath


class Config:
    log_root_path: str = abspath("logs")
    log_err_path: str = "err/err.log"
    log_out_path: str = "out/out.log"
    log_buffer_size: int = 64 * 1024
    log_max_file_size: int = 10 * 1024 * 1024
    instance_root_path: str = abspath("instances")
    data_root_path: str = abspath("datas")
    python_cmd: str = "python"
    template_root_path: str = abspath("templates")
    algorithm_root_path: str = abspath("algorithms")
    algorithm_info_path: str = ".info.json"