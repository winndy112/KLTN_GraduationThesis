import { Title, Text, Card, SimpleGrid, Tabs, Table, Badge, Group, Button, Drawer, ScrollArea, Code, Stack, Divider, TextInput, Modal, Select, Pagination } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { useDisclosure, useDebouncedValue } from '@mantine/hooks';
import { useState, useEffect } from 'react';
import { IconDatabase, IconBug, IconList, IconRefresh, IconSearch, IconDownload } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';
import { MISPStats, MISPEvent, MISPIOC } from '../api/types';

export default function CTI() {
    const { data: stats } = useQuery<MISPStats>({
        queryKey: ['misp-stats'],
        queryFn: async () => (await api.get('/misp/stats')).data,
    });

    const [searchEventId, setSearchEventId] = useState<string>('');
    const [debouncedSearchEventId] = useDebouncedValue(searchEventId, 500);
    const [eventPage, setEventPage] = useState<number>(1);

    const { data: eventsData, refetch: refetchEvents, isFetching: isFetchingEvents } = useQuery<{
        items: MISPEvent[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
    }>({
        queryKey: ['misp-events', debouncedSearchEventId, eventPage],
        queryFn: async () => {
            const params: any = { page: eventPage, page_size: 50 };
            if (debouncedSearchEventId) params.event_id = debouncedSearchEventId;
            return (await api.get('/misp/events', { params })).data;
        },
    });

    const events = eventsData?.items || [];

    // Reset to page 1 when search changes
    useEffect(() => {
        setEventPage(1);
    }, [debouncedSearchEventId]);

    const [iocPage, setIOCPage] = useState<number>(1);

    const { data: iocsData, refetch: refetchIOCs } = useQuery<{
        items: MISPIOC[];
        total: number;
        page: number;
        page_size: number;
        total_pages: number;
    }>({
        queryKey: ['misp-iocs', iocPage],
        queryFn: async () => (await api.get('/misp/iocs', { params: { page: iocPage, page_size: 50 } })).data,
    });

    const iocs = iocsData?.items || [];

    const [opened, { open, close }] = useDisclosure(false);
    const [selectedEvent, setSelectedEvent] = useState<MISPEvent | null>(null);

    const [iocOpened, { open: openIOC, close: closeIOC }] = useDisclosure(false);
    const [selectedIOC, setSelectedIOC] = useState<MISPIOC | null>(null);

    // Pull Modal State
    const [pullOpened, { open: openPull, close: closePull }] = useDisclosure(false);
    const [pullSince, setPullSince] = useState<string>('24h');
    const [pulling, setPulling] = useState(false);

    const handleRowClick = (event: MISPEvent) => {
        setSelectedEvent(event);
        open();
    };

    const handleIOCRowClick = (ioc: MISPIOC) => {
        setSelectedIOC(ioc);
        openIOC();
    };

    const handlePull = async () => {
        setPulling(true);
        try {
            await api.post('/misp/pull', null, { params: { since: pullSince } });
            notifications.show({ title: 'Success', message: 'Pull triggered successfully', color: 'green' });
            closePull();
            refetchEvents();
            refetchIOCs();
        } catch (e: any) {
            notifications.show({ title: 'Error', message: e.message || 'Pull failed', color: 'red' });
        } finally {
            setPulling(false);
        }
    };

    return (
        <Container fluid>
            <Group justify="space-between" mb="md">
                <Title order={2}>CTI Integration (MISP)</Title>
                <Group>
                    <Button variant="light" leftSection={<IconDownload size="1rem" />} onClick={openPull}>
                        Pull Data
                    </Button>
                    <Button variant="light" leftSection={<IconRefresh size="1rem" />} onClick={() => { refetchEvents(); refetchIOCs(); }}>
                        Refresh Data
                    </Button>
                </Group>
            </Group>

            <SimpleGrid cols={{ base: 1, sm: 3 }} mb="lg">
                <Card shadow="sm" padding="lg" radius="md" withBorder>
                    <Group justify="space-between" mb="xs">
                        <Text fw={500}>Total Events</Text>
                        <IconDatabase size="1.5rem" color="blue" />
                    </Group>
                    <Text size="xl" fw={700}>{stats?.events || 0}</Text>
                </Card>
                <Card shadow="sm" padding="lg" radius="md" withBorder>
                    <Group justify="space-between" mb="xs">
                        <Text fw={500}>Total IOCs</Text>
                        <IconBug size="1.5rem" color="red" />
                    </Group>
                    <Text size="xl" fw={700}>{stats?.iocs || 0}</Text>
                </Card>
                <Card shadow="sm" padding="lg" radius="md" withBorder>
                    <Group justify="space-between" mb="xs">
                        <Text fw={500}>Attributes</Text>
                        <IconList size="1.5rem" color="green" />
                    </Group>
                    <Text size="xl" fw={700}>{stats?.attributes || 0}</Text>
                </Card>
            </SimpleGrid>

            <Tabs defaultValue="events">
                <Tabs.List>
                    <Tabs.Tab value="events" leftSection={<IconDatabase size="0.8rem" />}>Events</Tabs.Tab>
                    <Tabs.Tab value="iocs" leftSection={<IconBug size="0.8rem" />}>IOCs</Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="events" pt="xs">
                    <Card shadow="sm" padding="lg" radius="md" withBorder>
                        <Group mb="md">
                            <TextInput
                                placeholder="Search by Event ID..."
                                leftSection={<IconSearch size="1rem" />}
                                value={searchEventId}
                                onChange={(event) => setSearchEventId(event.currentTarget.value)}
                                style={{ width: 300 }}
                            />
                        </Group>
                        <Table striped highlightOnHover>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Event ID</Table.Th>
                                    <Table.Th>Info</Table.Th>
                                    <Table.Th>ORG</Table.Th>
                                    <Table.Th>Pulled At</Table.Th>
                                    <Table.Th>IoCs count</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {events?.map((event) => (
                                    <Table.Tr key={event.uuid} onClick={() => handleRowClick(event)} style={{ cursor: 'pointer' }}>
                                        <Table.Td>{event.event_id}</Table.Td>
                                        <Table.Td>{event.info}</Table.Td>
                                        <Table.Td>{event.org}</Table.Td>
                                        <Table.Td>{event.source?.pulled_at ? new Date(event.source.pulled_at).toLocaleString() : '-'}</Table.Td>
                                        <Table.Td>{event.attribute_count}</Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                        {events?.length === 0 && !isFetchingEvents && (
                            <Text c="dimmed" ta="center" py="xl">No events found</Text>
                        )}
                        {eventsData && eventsData.total_pages > 1 && (
                            <Group justify="center" mt="md">
                                <Pagination
                                    total={eventsData.total_pages}
                                    value={eventPage}
                                    onChange={setEventPage}
                                />
                            </Group>
                        )}
                    </Card>
                </Tabs.Panel>

                <Tabs.Panel value="iocs" pt="xs">
                    <Card shadow="sm" padding="lg" radius="md" withBorder>
                        <Table striped highlightOnHover>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Value</Table.Th>
                                    <Table.Th>Type</Table.Th>
                                    <Table.Th>Category</Table.Th>
                                    <Table.Th>Event ID</Table.Th>
                                    <Table.Th>To IDs</Table.Th>
                                    <Table.Th>Source</Table.Th>
                                    <Table.Th>Timestamp</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {iocs?.map((ioc) => (
                                    <Table.Tr key={ioc.id || ioc.value} onClick={() => handleIOCRowClick(ioc)} style={{ cursor: 'pointer' }}>
                                        <Table.Td style={{ wordBreak: 'break-all' }}>{ioc.value}</Table.Td>
                                        <Table.Td><Badge variant="outline">{ioc.type}</Badge></Table.Td>
                                        <Table.Td>{ioc.category}</Table.Td>
                                        <Table.Td>{ioc.event_id || '-'}</Table.Td>
                                        <Table.Td>
                                            <Badge color={ioc.to_ids ? 'green' : 'gray'}>
                                                {ioc.to_ids ? 'Yes' : 'No'}
                                            </Badge>
                                        </Table.Td>
                                        <Table.Td>{ioc.source?.pulled_at ? new Date(ioc.source.pulled_at).toLocaleString() : '-'}</Table.Td>
                                        <Table.Td>{new Date(parseInt(ioc.timestamp) * 1000).toLocaleString()}</Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                        {iocsData && iocsData.total_pages > 1 && (
                            <Group justify="center" mt="md">
                                <Pagination
                                    total={iocsData.total_pages}
                                    value={iocPage}
                                    onChange={setIOCPage}
                                />
                            </Group>
                        )}
                    </Card>
                </Tabs.Panel>
            </Tabs>

            <Drawer opened={opened} onClose={close} title="Event Details" position="right" size="xl">
                {selectedEvent && (
                    <ScrollArea h="calc(100vh - 80px)">
                        <Stack gap="md">
                            <Group>
                                <Text fw={700}>Event ID:</Text>
                                <Text>{selectedEvent.event_id}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>UUID:</Text>
                                <Text size="sm" style={{ fontFamily: 'monospace' }}>{selectedEvent.uuid}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Info:</Text>
                                <Text>{selectedEvent.info}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Organization:</Text>
                                <Text>{selectedEvent.org}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Published:</Text>
                                <Badge color={selectedEvent.published ? 'green' : 'gray'}>
                                    {selectedEvent.published ? 'Yes' : 'No'}
                                </Badge>
                            </Group>
                            <Group>
                                <Text fw={700}>Timestamp:</Text>
                                <Text>{new Date(selectedEvent.timestamp).toLocaleString()}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Pulled At:</Text>
                                <Text>{selectedEvent.source?.pulled_at ? new Date(selectedEvent.source.pulled_at).toLocaleString() : '-'}</Text>
                            </Group>

                            <Divider my="sm" label="Tags" labelPosition="center" />
                            <Group gap="xs">
                                {selectedEvent.tags?.map((tag, i) => (
                                    <Badge key={i} variant="dot">{tag}</Badge>
                                ))}
                            </Group>

                            <Divider my="sm" label="Raw Data" labelPosition="center" />
                            <Code block>
                                {JSON.stringify(selectedEvent, null, 2)}
                            </Code>
                        </Stack>
                    </ScrollArea>
                )}
            </Drawer>

            <Drawer opened={iocOpened} onClose={closeIOC} title="IOC Details" position="right" size="xl">
                {selectedIOC && (
                    <ScrollArea h="calc(100vh - 80px)">
                        <Stack gap="md">
                            <Group>
                                <Text fw={700}>Value:</Text>
                                <Text style={{ wordBreak: 'break-all' }}>{selectedIOC.value}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Type:</Text>
                                <Badge variant="outline">{selectedIOC.type}</Badge>
                            </Group>
                            <Group>
                                <Text fw={700}>Category:</Text>
                                <Text>{selectedIOC.category}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>Event ID:</Text>
                                <Text>{selectedIOC.event_id || '-'}</Text>
                            </Group>
                            <Group>
                                <Text fw={700}>To IDs:</Text>
                                <Badge color={selectedIOC.to_ids ? 'green' : 'gray'}>
                                    {selectedIOC.to_ids ? 'Yes' : 'No'}
                                </Badge>
                            </Group>
                            <Group>
                                <Text fw={700}>Timestamp:</Text>
                                <Text>{new Date(parseInt(selectedIOC.timestamp) * 1000).toLocaleString()}</Text>
                            </Group>
                            {selectedIOC.source && (
                                <Group>
                                    <Text fw={700}>Pulled At:</Text>
                                    <Text>{new Date(selectedIOC.source.pulled_at).toLocaleString()}</Text>
                                </Group>
                            )}
                            {selectedIOC.comment && (
                                <Group>
                                    <Text fw={700}>Comment:</Text>
                                    <Text>{selectedIOC.comment}</Text>
                                </Group>
                            )}

                            <Divider my="sm" label="Raw Data" labelPosition="center" />
                            <Code block>
                                {JSON.stringify(selectedIOC, null, 2)}
                            </Code>
                        </Stack>
                    </ScrollArea>
                )}
            </Drawer>

            <Modal opened={pullOpened} onClose={closePull} title="Pull Data from MISP">
                <Stack>
                    <Select
                        label="Since"
                        description="Pull events updated since..."
                        data={[
                            { value: '1h', label: 'Last 1 hour' },
                            { value: '24h', label: 'Last 24 hours' },
                            { value: '7d', label: 'Last 7 days' },
                            { value: '30d', label: 'Last 30 days' },
                            { value: '1y', label: 'Last 1 year' },
                        ]}
                        value={pullSince}
                        onChange={(val) => setPullSince(val || '24h')}
                    />
                    <Button onClick={handlePull} loading={pulling} fullWidth>
                        Pull Now
                    </Button>
                </Stack>
            </Modal>
        </Container>
    );
}

import { Container } from '@mantine/core';
