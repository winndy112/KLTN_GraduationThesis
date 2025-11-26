import { Title, Table, Badge, Button, Group, ActionIcon, Tooltip, LoadingOverlay, Card, Drawer, ScrollArea, Stack, Text, Divider, Code } from '@mantine/core';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { IconRefresh, IconActivity } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';
import { Sensor } from '../api/types';
import { useDisclosure } from '@mantine/hooks';
import { useState } from 'react';

export default function Sensors() {
    const queryClient = useQueryClient();
    const [opened, { open, close }] = useDisclosure(false);
    const [selectedSensor, setSelectedSensor] = useState<Sensor | null>(null);

    const { data: sensors, isLoading, isError } = useQuery<Sensor[]>({
        queryKey: ['sensors'],
        queryFn: async () => {
            const res = await api.get('/sensors/');
            return res.data;
        },
        refetchInterval: 10000, // Poll every 10s
    });

    const checkNowMutation = useMutation({
        mutationFn: async (sensorId: string) => {
            await api.get(`/sensors/${sensorId}/check_now`);
        },
        onSuccess: () => {
            notifications.show({
                title: 'Success',
                message: 'Sensor status checked successfully',
                color: 'green',
            });
            queryClient.invalidateQueries({ queryKey: ['sensors'] });
        },
        onError: () => {
            notifications.show({
                title: 'Error',
                message: 'Failed to check sensor status',
                color: 'red',
            });
        },
    });

    const handleRowClick = (sensor: Sensor) => {
        setSelectedSensor(sensor);
        open();
    };

    if (isError) {
        return <Title c="red">Error loading sensors</Title>;
    }

    const rows = sensors?.map((sensor) => (
        <Table.Tr key={sensor.sensor_id} onClick={() => handleRowClick(sensor)} style={{ cursor: 'pointer' }}>
            <Table.Td>{sensor.sensor_id}</Table.Td>
            <Table.Td>{sensor.hostname}</Table.Td>
            <Table.Td>{sensor.ip_mgmt || 'N/A'}</Table.Td>
            <Table.Td>
                <Badge
                    color={
                        sensor.status === 'active'
                            ? 'green'
                            : sensor.status === 'dormant'
                                ? 'yellow'
                                : 'red'
                    }
                >
                    {sensor.status}
                </Badge>
            </Table.Td>
            <Table.Td>{sensor.last_heartbeat ? new Date(sensor.last_heartbeat).toLocaleString() : 'Never'}</Table.Td>
            <Table.Td>{sensor.rule_version || 'N/A'}</Table.Td>
            <Table.Td onClick={(e) => e.stopPropagation()}>
                <Tooltip label="Check Status Now">
                    <ActionIcon
                        variant="light"
                        color="blue"
                        onClick={() => checkNowMutation.mutate(sensor.sensor_id)}
                        loading={checkNowMutation.isPending}
                    >
                        <IconActivity size="1rem" />
                    </ActionIcon>
                </Tooltip>
            </Table.Td>
        </Table.Tr>
    ));

    return (
        <>
            <Card shadow="sm" padding="lg" radius="md" withBorder>
                <LoadingOverlay visible={isLoading} />
                <Group justify="space-between" mb="md">
                    <Title order={2}>Sensors</Title>
                    <Button
                        leftSection={<IconRefresh size="1rem" />}
                        variant="light"
                        onClick={() => queryClient.invalidateQueries({ queryKey: ['sensors'] })}
                    >
                        Refresh
                    </Button>
                </Group>

                <Table striped highlightOnHover>
                    <Table.Thead>
                        <Table.Tr>
                            <Table.Th>ID</Table.Th>
                            <Table.Th>Hostname</Table.Th>
                            <Table.Th>IP Mgmt</Table.Th>
                            <Table.Th>Status</Table.Th>
                            <Table.Th>Last Heartbeat</Table.Th>
                            <Table.Th>Rule Version</Table.Th>
                            <Table.Th>Actions</Table.Th>
                        </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>{rows}</Table.Tbody>
                </Table>
            </Card>

            <Drawer opened={opened} onClose={close} title="Sensor Details" position="right" size="xl">
                {selectedSensor && (
                    <ScrollArea h="calc(100vh - 80px)">
                        <Stack gap="md">
                            <Group>
                                <Text fw={700}>Sensor ID:</Text>
                                <Text>{selectedSensor.sensor_id}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Hostname:</Text>
                                <Text>{selectedSensor.hostname}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>IP Management:</Text>
                                <Text>{selectedSensor.ip_mgmt || 'N/A'}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Status:</Text>
                                <Badge
                                    color={
                                        selectedSensor.status === 'active'
                                            ? 'green'
                                            : selectedSensor.status === 'dormant'
                                                ? 'yellow'
                                                : 'red'
                                    }
                                >
                                    {selectedSensor.status}
                                </Badge>
                            </Group>
                            <Group>
                                <Text fw={700}>Last Heartbeat:</Text>
                                <Text>{selectedSensor.last_heartbeat ? new Date(selectedSensor.last_heartbeat).toLocaleString() : 'Never'}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Rule Version:</Text>
                                <Text>{selectedSensor.rule_version || 'N/A'}</Text>
                            </Group>

                            <Divider my="sm" label="System Resources" labelPosition="center" />

                            <Group>
                                <Text fw={700}>CPU Usage:</Text>
                                <Text>{selectedSensor.cpu_pct !== undefined ? `${selectedSensor.cpu_pct}%` : 'N/A'}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Memory Usage:</Text>
                                <Text>{selectedSensor.mem_pct !== undefined ? `${selectedSensor.mem_pct}%` : 'N/A'}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Disk Free:</Text>
                                <Text>{selectedSensor.disk_free_gb !== undefined ? `${selectedSensor.disk_free_gb} GB` : 'N/A'}</Text>
                            </Group>

                            <Divider my="sm" label="Raw Data" labelPosition="center" />
                            <Code block>
                                {JSON.stringify(selectedSensor, null, 2)}
                            </Code>
                        </Stack>
                    </ScrollArea>
                )}
            </Drawer>
        </>
    );
}
