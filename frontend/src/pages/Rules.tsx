import { useState } from 'react';
import { Title, Tabs, Table, Badge, Button, Group, TextInput, ActionIcon, Tooltip, Card, LoadingOverlay, NumberInput, Divider, Code, Text, SegmentedControl, Select } from '@mantine/core';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { IconGavel, IconList, IconSearch, IconCloudUpload, IconHammer, IconTransform } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { api } from '../api/client';
import { RuleSet, RuleItem } from '../api/types';

export default function Rules() {
    const queryClient = useQueryClient();

    // --- View Mode State ---
    const [viewMode, setViewMode] = useState<'search' | 'version'>('search');
    const [keyword, setKeyword] = useState('');
    const [iocType, setIocType] = useState('');
    const [selectedVersion, setSelectedVersion] = useState<string | null>(null);

    // --- Rule Sets ---
    const { data: ruleSetsData, isLoading: isLoadingSets } = useQuery<{ sets: RuleSet[] }>({
        queryKey: ['rule-sets'],
        queryFn: async () => (await api.get('/rules/sets')).data,
    });

    // --- Rule Items ---
    const { data: ruleItems, isLoading: isLoadingItems } = useQuery<RuleItem[]>({
        queryKey: ['rule-items', viewMode, keyword, iocType, selectedVersion],
        queryFn: async () => {
            if (viewMode === 'search') {
                const params: any = { limit: 50 };
                if (keyword) params.keyword = keyword;
                if (iocType) params.ioc_type = iocType;
                return (await api.get('/rules/items', { params })).data;
            } else {
                if (!selectedVersion) return [];
                const res = await api.get(`/rules/sets/${selectedVersion}/items`, { params: { limit: 100 } });
                return res.data.items || [];
            }
        },
        enabled: viewMode === 'search' || !!selectedVersion,
    });

    // --- Convert State ---
    const [convertEventId, setConvertEventId] = useState<number | ''>('');
    const [convertResult, setConvertResult] = useState<string>('');
    const [converting, setConverting] = useState(false);

    const handleConvert = async () => {
        setConverting(true);
        setConvertResult('');
        try {
            const params: any = {};
            if (convertEventId) params.event_id = convertEventId;
            const res = await api.post('/rules/convert', null, { params });
            setConvertResult(JSON.stringify(res.data, null, 2));
            notifications.show({ title: 'Success', message: 'Conversion completed', color: 'green' });
            queryClient.invalidateQueries({ queryKey: ['rule-items'] });
        } catch (e: any) {
            notifications.show({ title: 'Error', message: e.message || 'Conversion failed', color: 'red' });
            setConvertResult(JSON.stringify(e.response?.data || e.message, null, 2));
        } finally {
            setConverting(false);
        }
    };

    // --- Mutations ---
    const buildMutation = useMutation({
        mutationFn: async (version: string) => await api.post(`/rules/${version}/build`),
        onSuccess: () => {
            notifications.show({ title: 'Success', message: 'Rule set built successfully', color: 'green' });
            queryClient.invalidateQueries({ queryKey: ['rule-sets'] });
        },
    });

    const deployMutation = useMutation({
        mutationFn: async (version: string) => await api.post(`/rules/${version}/deploy`, { target: 'all' }),
        onSuccess: () => {
            notifications.show({ title: 'Success', message: 'Rule set deployed successfully', color: 'green' });
            queryClient.invalidateQueries({ queryKey: ['rule-sets'] });
        },
    });

    return (
        <Container fluid>
            <Group justify="space-between" mb="md">
                <Title order={2}>Rules Engine</Title>
            </Group>

            <Tabs defaultValue="sets">
                <Tabs.List>
                    <Tabs.Tab value="sets" leftSection={<IconGavel size="0.8rem" />}>Rule Sets</Tabs.Tab>
                    <Tabs.Tab value="items" leftSection={<IconList size="0.8rem" />}>Rule Items</Tabs.Tab>
                    <Tabs.Tab value="convert" leftSection={<IconTransform size="0.8rem" />}>Convert Rules</Tabs.Tab>
                </Tabs.List>

                <Tabs.Panel value="sets" pt="xs">
                    <Card shadow="sm" padding="lg" radius="md" withBorder>
                        <LoadingOverlay visible={isLoadingSets} />
                        <Table striped highlightOnHover>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>Version</Table.Th>
                                    <Table.Th>Name</Table.Th>
                                    <Table.Th>Items</Table.Th>
                                    <Table.Th>Status</Table.Th>
                                    <Table.Th>Actions</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {ruleSetsData?.sets?.map((set) => (
                                    <Table.Tr key={set._id}>
                                        <Table.Td>{set.version}</Table.Td>
                                        <Table.Td>{set.name}</Table.Td>
                                        <Table.Td>{set.item_count}</Table.Td>
                                        <Table.Td>
                                            <Badge color={set.status === 'active' ? 'green' : 'blue'}>{set.status}</Badge>
                                        </Table.Td>
                                        <Table.Td>
                                            <Group gap="xs">
                                                <Tooltip label="Build">
                                                    <ActionIcon variant="light" color="orange" onClick={() => buildMutation.mutate(set.version)}>
                                                        <IconHammer size="1rem" />
                                                    </ActionIcon>
                                                </Tooltip>
                                                <Tooltip label="Deploy">
                                                    <ActionIcon variant="light" color="green" onClick={() => deployMutation.mutate(set.version)}>
                                                        <IconCloudUpload size="1rem" />
                                                    </ActionIcon>
                                                </Tooltip>
                                            </Group>
                                        </Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    </Card>
                </Tabs.Panel>

                <Tabs.Panel value="items" pt="xs">
                    <Card shadow="sm" padding="lg" radius="md" withBorder>
                        <Group mb="md">
                            <SegmentedControl
                                value={viewMode}
                                onChange={(val: any) => setViewMode(val)}
                                data={[
                                    { label: 'Search', value: 'search' },
                                    { label: 'By Version', value: 'version' },
                                ]}
                            />
                            {viewMode === 'search' ? (
                                <>
                                    <TextInput
                                        placeholder="Keyword..."
                                        leftSection={<IconSearch size="1rem" />}
                                        value={keyword}
                                        onChange={(e) => setKeyword(e.currentTarget.value)}
                                        style={{ flexGrow: 1 }}
                                    />
                                    <TextInput
                                        placeholder="IOC Type (optional)"
                                        value={iocType}
                                        onChange={(e) => setIocType(e.currentTarget.value)}
                                        style={{ width: 200 }}
                                    />
                                </>
                            ) : (
                                <Select
                                    placeholder="Select Rule Set Version"
                                    data={ruleSetsData?.sets?.map(s => s.version) || []}
                                    value={selectedVersion}
                                    onChange={setSelectedVersion}
                                    style={{ flexGrow: 1 }}
                                    searchable
                                />
                            )}
                        </Group>
                        <LoadingOverlay visible={isLoadingItems} />
                        <Table striped highlightOnHover>
                            <Table.Thead>
                                <Table.Tr>
                                    <Table.Th>SID</Table.Th>
                                    <Table.Th>Message</Table.Th>
                                    <Table.Th>Rule Text</Table.Th>
                                </Table.Tr>
                            </Table.Thead>
                            <Table.Tbody>
                                {ruleItems?.length === 0 && !isLoadingItems && (
                                    <Table.Tr>
                                        <Table.Td colSpan={3} style={{ textAlign: 'center', color: 'gray' }}>
                                            {viewMode === 'version' && !selectedVersion ? 'Select a version to view items' : 'No items found'}
                                        </Table.Td>
                                    </Table.Tr>
                                )}
                                {ruleItems?.map((item) => (
                                    <Table.Tr key={item.id || item.sid}>
                                        <Table.Td>{item.sid}</Table.Td>
                                        <Table.Td>{item.msg}</Table.Td>
                                        <Table.Td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{item.rule_text}</Table.Td>
                                    </Table.Tr>
                                ))}
                            </Table.Tbody>
                        </Table>
                    </Card>
                </Tabs.Panel>

                <Tabs.Panel value="convert" pt="xs">
                    <Card shadow="sm" padding="lg" radius="md" withBorder>
                        <Title order={4} mb="md">Convert IoCs to Rules</Title>
                        <Text c="dimmed" mb="lg">
                            Convert IoCs from MISP events into Snort rules. You can specify an Event ID to convert only that event, or leave it empty to convert all new events.
                        </Text>

                        <Group align="flex-end" mb="xl">
                            <NumberInput
                                label="Event ID (Optional)"
                                placeholder="Leave empty for all events"
                                value={convertEventId}
                                onChange={(val) => setConvertEventId(val === '' ? '' : Number(val))}
                                min={1}
                                style={{ width: 300 }}
                            />
                            <Button
                                onClick={handleConvert}
                                loading={converting}
                                leftSection={<IconTransform size="1rem" />}
                            >
                                Convert Rules
                            </Button>
                        </Group>

                        {convertResult && (
                            <>
                                <Divider my="md" label="Conversion Result" labelPosition="center" />
                                <Code block style={{ maxHeight: '400px', overflowY: 'auto' }}>
                                    {convertResult}
                                </Code>
                            </>
                        )}
                    </Card>
                </Tabs.Panel>
            </Tabs>
        </Container>
    );
}

import { Container } from '@mantine/core';
