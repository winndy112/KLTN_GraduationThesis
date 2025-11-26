import { useState, useEffect } from 'react';
import { Title, Table, Group, Card, LoadingOverlay, Text, Pagination, Container, Badge } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { IconAlertTriangle } from '@tabler/icons-react';
import { api } from '../api/client';
import { Alert } from '../api/types';
import TimeRangeSelector, { TimeRangeValue } from '../components/TimeRangeSelector';
import AdvancedSearchBar from '../components/AdvancedSearchBar';

export default function Alerts() {
    const [filterExpression, setFilterExpression] = useState('');
    const [timeRange, setTimeRange] = useState<TimeRangeValue>({
        mode: 'preset',
        presetMinutes: 60,
    });
    const [page, setPage] = useState(1);

    // Reset page when filters change
    useEffect(() => {
        setPage(1);
    }, [filterExpression, timeRange]);

    // Build query parameters based on time range mode
    const buildQueryParams = () => {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const params: any = {
            page: page,
            page_size: 50,
        };

        // Add filter expression if present
        if (filterExpression.trim()) {
            params.filters = filterExpression.trim();
        }

        // Add time range parameters based on mode
        if (timeRange.mode === 'realtime') {
            params.realtime = true;
        } else if (timeRange.mode === 'custom' && timeRange.fromTime && timeRange.toTime) {
            params.from_time = timeRange.fromTime.toISOString();
            params.to_time = timeRange.toTime.toISOString();
        } else if (timeRange.mode === 'preset' && timeRange.presetMinutes) {
            params.since_minutes = timeRange.presetMinutes;
        }

        return params;
    };

    const { data: alertsData, isLoading } = useQuery<{
        items: Alert[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
    }>({
        queryKey: ['alerts', filterExpression, timeRange, page],
        queryFn: async () => (await api.get('/alerts/recent', {
            params: buildQueryParams()
        })).data,
        // Faster polling for real-time mode
        refetchInterval: timeRange.mode === 'realtime' ? 2000 : 5000,
    });

    const alerts = alertsData?.items || [];

    return (
        <Container fluid>
            <Title order={2} mb="md">Alerts</Title>

            <Card shadow="sm" padding="lg" radius="md" withBorder mb="lg">
                <Group mb="md" align="flex-start">
                    <AdvancedSearchBar
                        value={filterExpression}
                        onChange={setFilterExpression}
                    />
                    <TimeRangeSelector
                        value={timeRange}
                        onChange={setTimeRange}
                    />
                </Group>

                <LoadingOverlay visible={isLoading} />

                {alerts?.length === 0 && !isLoading && (
                    <Text ta="center" c="dimmed" py="xl">No alerts found matching your criteria.</Text>
                )}

                {alerts && alerts.length > 0 && (
                    <Table striped highlightOnHover>
                        <Table.Thead>
                            <Table.Tr>
                                <Table.Th>Time</Table.Th>
                                <Table.Th>Priority</Table.Th>
                                <Table.Th>Action</Table.Th>
                                <Table.Th>Rule ID</Table.Th>
                                <Table.Th>Message</Table.Th>
                                <Table.Th>Source</Table.Th>
                                <Table.Th>Destination</Table.Th>
                                <Table.Th>Sensor</Table.Th>
                            </Table.Tr>
                        </Table.Thead>
                        <Table.Tbody>
                            {alerts.map((alert) => (
                                <Table.Tr key={alert._id}>
                                    <Table.Td style={{ whiteSpace: 'nowrap' }}>
                                        {new Date(alert.ingested_at || alert.ts).toLocaleString()}
                                    </Table.Td>
                                    <Table.Td>
                                        <Badge
                                            color={
                                                (alert.priority || 3) === 1 ? 'red' :
                                                    (alert.priority || 3) === 2 ? 'orange' :
                                                        'blue'
                                            }
                                            variant="light"
                                        >
                                            P{alert.priority || 3}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>
                                        <Badge
                                            color={
                                                alert.action === 'block' || alert.action === 'drop' ? 'red' :
                                                    alert.action === 'allow' ? 'green' :
                                                        'gray'
                                            }
                                            variant="dot"
                                        >
                                            {alert.action || 'unknown'}
                                        </Badge>
                                    </Table.Td>
                                    <Table.Td>{alert.rule_id}</Table.Td>
                                    <Table.Td>
                                        <Group gap="xs" wrap="nowrap">
                                            <IconAlertTriangle size="0.8rem" color="orange" style={{ flexShrink: 0 }} />
                                            <Text size="sm" lineClamp={2} title={alert.msg}>
                                                {alert.msg}
                                            </Text>
                                        </Group>
                                    </Table.Td>
                                    <Table.Td>{alert.src.ip}:{alert.src.port}</Table.Td>
                                    <Table.Td>{alert.dst.ip}:{alert.dst.port}</Table.Td>
                                    <Table.Td>{alert.sensor_id}</Table.Td>
                                </Table.Tr>
                            ))}
                        </Table.Tbody>
                    </Table>
                )}

                {alertsData && alertsData.total_pages > 1 && (
                    <Group justify="center" mt="md">
                        <Pagination
                            total={alertsData.total_pages}
                            value={page}
                            onChange={setPage}
                        />
                    </Group>
                )}
            </Card>
        </Container>
    );
}
