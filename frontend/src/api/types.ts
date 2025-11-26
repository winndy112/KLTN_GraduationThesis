export interface Sensor {
    sensor_id: string;
    hostname: string;
    status: 'active' | 'inactive' | 'dormant';
    ip_mgmt?: string;
    last_heartbeat?: string;
    rule_version?: string;
    cpu_pct?: number;
    mem_pct?: number;
    disk_free_gb?: number;
}

export interface Alert {
    _id: string;
    ts: string;
    sensor_id: string;
    rule_id: string;
    msg: string;
    src: { ip?: string; port?: number };
    dst: { ip?: string; port?: number };
    priority?: number;
    action?: string;
    ingested_at?: string;
}

export interface MISPStats {
    events: number;
    iocs: number;
    attributes: number;
}

export interface MISPEvent {
    event_id: number;
    uuid: string;
    info: string;
    org: string;
    orgc: string;
    published: boolean;
    attribute_count: number;
    timestamp: string;
    tags: string[];
    source: {
        misp_url: string;
        pulled_at: string;
    };
    galaxies: any[];
}

export interface MISPIOC {
    id: string;
    value: string;
    type: string;
    category: string;
    timestamp: string;
    comment?: string;
    event_id?: number;
    to_ids?: boolean;
    source?: {
        misp_url: string;
        pulled_at: string;
    };
}

export interface RuleItem {
    id: string;
    sid: number;
    msg: string;
    rule_text: string;
    metadata: Record<string, any>;
}

export interface RuleSet {
    _id: string;
    name: string;
    version: string;
    item_count: number;
    status: string;
}
