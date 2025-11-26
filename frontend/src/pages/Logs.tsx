import { useState, useEffect, useRef } from 'react';
import {
    Table, Button, Select, Group, Title, Paper, Stack, Badge, Loader, Text, Pagination
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconPlayerPlay, IconPlayerPause, IconSearch } from '@tabler/icons-react';

// Helper to format epoch
const formatTs = (ts: number) => new Date(ts * 1000).toLocaleString();

interface LogEntry {
    ts: number;
    uid: string;
    "id.orig_h": string;
    "id.orig_p": number;
    "id.resp_h": string;
    "id.resp_p": number;
    proto: string;
    service: string;
    _sensor_hostname?: string;
    [key: string]: any;
}

export default function Logs() {
    const [mode, setMode] = useState<'live' | 'history'>('live');
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [cursor, setCursor] = useState(0);
    const [isPolling, setIsPolling] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(0);

    // History filters
    const [dateRange, setDateRange] = useState<[Date | null, Date | null]>([
        new Date(Date.now() - 3600000), // 1 hour ago
        new Date()
    ]);

    const pollInterval = useRef<number | null>(null);

    const fetchLogs = async (isPoll = false) => {
        if (loading && !isPoll) return;
        if (!isPoll) setLoading(true);

        try {
            const params = new URLSearchParams({
                mode: mode,
                page: page.toString(),
                page_size: '50'
            });

            if (mode === 'live') {
                params.append('cursor', cursor.toString());
            } else {
                if (dateRange[0]) params.append('start_ts', (dateRange[0].getTime() / 1000).toString());
                if (dateRange[1]) params.append('end_ts', (dateRange[1].getTime() / 1000).toString());
            }

            const res = await fetch(`/api/v1/logs/query?${params.toString()}`);
            const data = await res.json();

            if (data.items && data.items.length > 0) {
                if (mode === 'live') {
                    // Prepend new logs
                    setLogs(prev => [...data.items, ...prev].slice(0, 500)); // Keep last 500
                    setCursor(data.next_cursor);
                } else {
                    setLogs(data.items);
                    setTotalPages(data.total_pages || 0);
                }
            }
        } catch (err) {
            console.error("Failed to fetch logs", err);
        } finally {
            if (!isPoll) setLoading(false);
        }
    };

    // Effect for Live Polling
    useEffect(() => {
        if (mode === 'live' && isPolling) {
            fetchLogs(); // Initial fetch
            pollInterval.current = window.setInterval(() => {
                fetchLogs(true);
            }, 5000);
        } else {
            if (pollInterval.current) clearInterval(pollInterval.current);
        }
        return () => {
            if (pollInterval.current) clearInterval(pollInterval.current);
        };
    }, [mode, isPolling]);

    // Reset when switching modes
    useEffect(() => {
        setLogs([]);
        setCursor(0);
        if (mode === 'live') {
            setIsPolling(true);
        } else {
            setIsPolling(false);
        }
    }, [mode]);

    const rows = logs.map((log, idx) => (
        <Table.Tr key={`${log.uid}-${idx}`}>
            <Table.Td>{formatTs(log.ts)}</Table.Td>
            <Table.Td>{log._sensor_hostname || 'Unknown'}</Table.Td>
            <Table.Td>{log["id.orig_h"]}:{log["id.orig_p"]}</Table.Td>
            <Table.Td>{log["id.resp_h"]}:{log["id.resp_p"]}</Table.Td>
            <Table.Td><Badge variant="light">{log.proto}</Badge></Table.Td>
            <Table.Td>{log.service}</Table.Td>
            <Table.Td style={{ fontFamily: 'monospace' }}>{log.uid}</Table.Td>
        </Table.Tr>
    ));

    return (
        <Stack p="md">
            <Group justify="space-between" align="center">
                <Title order={2}>Log Search</Title>
                <Group>
                    <Select
                        value={mode}
                        onChange={(val) => setMode(val as 'live' | 'history')}
                        data={[
                            { value: 'live', label: 'Live' },
                            { value: 'history', label: 'History' }
                        ]}
                        w={120}
                    />

                    {mode === 'live' && (
                        <Button
                            color={isPolling ? "yellow" : "green"}
                            leftSection={isPolling ? <IconPlayerPause size={16} /> : <IconPlayerPlay size={16} />}
                            onClick={() => setIsPolling(!isPolling)}
                        >
                            {isPolling ? "Pause" : "Resume"}
                        </Button>
                    )}

                    {mode === 'history' && (
                        <>
                            <DatePickerInput
                                type="range"
                                placeholder="Pick dates range"
                                value={dateRange}
                                onChange={(val) => setDateRange(val as [Date | null, Date | null])}
                                w={300}
                            />
                            <Button leftSection={<IconSearch size={16} />} onClick={() => fetchLogs()}>
                                Search
                            </Button>
                        </>
                    )}
                </Group>
            </Group>

            <Paper shadow="xs" p="md" withBorder>
                <Table stickyHeader>
                    <Table.Thead>
                        <Table.Tr>
                            <Table.Th>Time</Table.Th>
                            <Table.Th>Sensor</Table.Th>
                            <Table.Th>Source</Table.Th>
                            <Table.Th>Dest</Table.Th>
                            <Table.Th>Proto</Table.Th>
                            <Table.Th>Service</Table.Th>
                            <Table.Th>Info</Table.Th>
                        </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                        {rows}
                        {logs.length === 0 && !loading && (
                            <Table.Tr>
                                <Table.Td colSpan={7} align="center">
                                    <Text c="dimmed">No logs found</Text>
                                </Table.Td>
                            </Table.Tr>
                        )}
                    </Table.Tbody>
                </Table>
                {loading && <Group justify="center" p="md"><Loader size="sm" /></Group>}
                {mode === 'history' && totalPages > 1 && (
                    <Group justify="center" mt="md">
                        <Pagination
                            total={totalPages}
                            value={page}
                            onChange={setPage}
                        />
                    </Group>
                )}
            </Paper>
        </Stack>
    );
}
