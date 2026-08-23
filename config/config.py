class Config:
    class UserNodeConfig:
        # Frequency of local vehicle CPU (e.g., in GHz or cycles per second)
        USER_NODE_FREQUENCY: float = 2.0  

    class MobileFogNodeConfig:
        # Frequency of Fog Node CPU (e.g., in GHz or cycles per second)
        MOBILE_NODE_FREQUENCY: float = 5.0