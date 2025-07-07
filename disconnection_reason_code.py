def disconnection_reason_code(code):
    reason_code_dict = {
        0: "Reserved",
        1: "Unspecified reason",
        2: "Previous authentication no longer valid",
        3: "Station is leaving (or has left) IBSS or ESS",
        4: "Disassociated due to inactivity",
        5: "Disassociated because AP is unable to handle all currently associated stations",
        6: "Class 2 frame received from nonauthenticated station",
        7: "Class 3 frame received from nonassociated station",
        8: "Disassociated because sending station is leaving (or has left) BSS",
        9: "Station requesting (re)association is not authenticated with responding station",
        10: "Disassociated: Power Capability element unacceptable",
        11: "Disassociated: Supported Channels element unacceptable",
        12: "Reserved",
        13: "Invalid information element",
        14: "Message integrity code (MIC) failure",
        15: "4-Way Handshake timeout",
        16: "Group Key Handshake timeout",
        17: "Info element in handshake differs from Association/Probe/Beacon",
        18: "Invalid group cipher",
        19: "Invalid pairwise cipher",
        20: "Invalid AKMP",
        21: "Unsupported RSN IE version",
        22: "Invalid RSN IE capabilities",
        23: "IEEE 802.1X authentication failed",
        24: "Cipher suite rejected by security policy",
        32: "Disassociated for unspecified QoS-related reason",
        33: "QAP lacks sufficient bandwidth for QSTA",
        34: "Too many unacknowledged frames",
        35: "QSTA transmitting outside TXOP limits",
        36: "Peer QSTA requested disassociation (leaving QBSS/reset)",
        37: "Peer QSTA requested disassociation (mechanism refusal)",
        38: "Peer QSTA received frames using setup-required mechanism",
        39: "Peer QSTA timeout",
        40: "Peer QSTA doesn't support requested cipher suite",
        98: "Cisco defined",
        99: "Cisco defined (invalid reason code sent by client)",
    }

    if code in reason_code_dict:
        return reason_code_dict[code]
    elif 25 <= code <= 31 or 46 <= code <= 65535:
        return "Reserved"
    else:
        return "Unknown Reason Code"