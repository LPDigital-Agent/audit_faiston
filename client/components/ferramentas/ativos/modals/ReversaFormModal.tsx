'use client';

// =============================================================================
// ReversaFormModal - Reversa (Reverse Logistics) E-Ticket Generation
// =============================================================================
// SCAFFOLD - Submit logic blocked pending VIPP confirmation on:
// 1. Remetente structure inside Volumes[]
// 2. TipoAutorizacaoReversa values
// 3. E-ticket field location in response
//
// Form for generating reverse logistics e-tickets (PAC REVERSA / SEDEX REVERSA).
// Pre-fills technician data from Tiflux ticket, user completes package details.
// =============================================================================

import { useState, useEffect, useCallback, startTransition } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Package,
  User,
  Phone,
  MapPin,
  Scale,
  Ruler,
  DollarSign,
  FileText,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { COST_CENTERS } from '@/lib/ativos/cost-centers';
import type { TifluxTicketDetail } from '@/lib/ativos/types';

// =============================================================================
// Types
// =============================================================================

interface ReversaFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  ticket?: TifluxTicketDetail | null;
}

interface ReversaFormState {
  // Remetente Information (pre-filled from ticket)
  // Matches VIPP form fields: CNPJ/CPF, Nome, CEP, Endereço, Número, Complemento, Bairro, Cidade, UF, Telefone, Celular, Email
  cpfCnpj: string;        // CPF or CNPJ
  name: string;           // Nome
  cep: string;            // CEP
  address: string;        // Endereço
  number: string;         // Número
  complement: string;     // Complemento
  neighborhood: string;   // Bairro
  city: string;           // Cidade
  state: string;          // UF
  phone: string;          // Telefone
  mobile: string;         // Celular
  email: string;          // Email

  // Destinatario Information (user input - destination address)
  destCpfCnpj: string;    // CPF or CNPJ
  destName: string;       // Nome
  destCep: string;        // CEP
  destAddress: string;    // Endereço
  destNumber: string;     // Número
  destComplement: string; // Complemento
  destNeighborhood: string; // Bairro
  destCity: string;       // Cidade
  destState: string;      // UF
  destPhone: string;      // Telefone
  destMobile: string;     // Celular
  destEmail: string;      // Email

  // Package Information (user input)
  weight: string;         // kg (required)
  height: string;         // cm (optional)
  width: string;          // cm (optional)
  length: string;         // cm (optional)
  declaredValue: string;  // BRL (optional)

  // Service Options (user input)
  serviceType: 'PAC_REVERSA' | 'SEDEX_REVERSA';
  costCenter: string;
  notes: string;
}

// =============================================================================
// Component
// =============================================================================

export function ReversaFormModal({
  open,
  onOpenChange,
  ticket,
}: ReversaFormModalProps) {
  const [formData, setFormData] = useState<ReversaFormState>({
    // Remetente fields (matches VIPP form)
    cpfCnpj: '',
    name: '',
    cep: '',
    address: '',
    number: '',
    complement: '',
    neighborhood: '',
    city: '',
    state: '',
    phone: '',
    mobile: '',
    email: '',
    // Destinatario fields
    destCpfCnpj: '',
    destName: '',
    destCep: '',
    destAddress: '',
    destNumber: '',
    destComplement: '',
    destNeighborhood: '',
    destCity: '',
    destState: '',
    destPhone: '',
    destMobile: '',
    destEmail: '',
    // Package fields
    weight: '',
    height: '',
    width: '',
    length: '',
    declaredValue: '',
    // Service options
    serviceType: 'PAC_REVERSA',
    costCenter: COST_CENTERS[0].id,
    notes: '',
  });

  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // =============================================================================
  // Effects
  // =============================================================================

  /**
   * Pre-fill form data from ticket when ticket changes
   * Maps Tiflux technician data to VIPP Remetente fields
   */
  useEffect(() => {
    if (ticket?.technician) {
      startTransition(() => {
        setFormData((prev) => ({
          ...prev,
          cpfCnpj: ticket.technician?.cpf || '',
          name: ticket.technician?.nome || '',
          cep: ticket.technician?.cep || '',
          address: ticket.technician?.endereco || '',
          number: ticket.technician?.numero || '',
          complement: ticket.technician?.complemento || '',
          neighborhood: ticket.technician?.bairro || '',
          city: ticket.technician?.cidade || '',
          state: ticket.technician?.uf || '',
          phone: ticket.technician?.telefone || '',
          mobile: '', // Not available in TifluxTechnicianData
          email: ticket.technician?.email || '',
        }));
      });
    }
  }, [ticket]);

  /**
   * Reset form when modal closes
   */
  useEffect(() => {
    if (!open) {
      startTransition(() => {
        setErrors({});
        // Reset user input fields (keep pre-filled remetente data)
        setFormData((prev) => ({
          ...prev,
          // Reset destinatario fields
          destCpfCnpj: '',
          destName: '',
          destCep: '',
          destAddress: '',
          destNumber: '',
          destComplement: '',
          destNeighborhood: '',
          destCity: '',
          destState: '',
          destPhone: '',
          destMobile: '',
          destEmail: '',
          // Reset package fields
          weight: '',
          height: '',
          width: '',
          length: '',
          declaredValue: '',
          serviceType: 'PAC_REVERSA',
          costCenter: COST_CENTERS[0].id,
          notes: '',
        }));
      });
    }
  }, [open]);

  // =============================================================================
  // Handlers
  // =============================================================================

  const handleInputChange = useCallback((field: keyof ReversaFormState, value: string) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    // Clear error for this field
    if (errors[field]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[field];
        return next;
      });
    }
  }, [errors]);

  const validateForm = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    // Required Remetente fields (matches VIPP requirements)
    if (!formData.cpfCnpj.trim()) newErrors.cpfCnpj = 'CPF/CNPJ é obrigatório';
    if (!formData.name.trim()) newErrors.name = 'Nome é obrigatório';
    if (!formData.cep.trim()) newErrors.cep = 'CEP é obrigatório';
    if (!formData.address.trim()) newErrors.address = 'Endereço é obrigatório';
    if (!formData.number.trim()) newErrors.number = 'Número é obrigatório';
    if (!formData.neighborhood.trim()) newErrors.neighborhood = 'Bairro é obrigatório';
    if (!formData.city.trim()) newErrors.city = 'Cidade é obrigatória';
    if (!formData.state.trim()) newErrors.state = 'UF é obrigatório';
    if (!formData.phone.trim()) newErrors.phone = 'Telefone é obrigatório';

    // Required Destinatario fields
    if (!formData.destCpfCnpj.trim()) newErrors.destCpfCnpj = 'CPF/CNPJ é obrigatório';
    if (!formData.destName.trim()) newErrors.destName = 'Nome é obrigatório';
    if (!formData.destCep.trim()) newErrors.destCep = 'CEP é obrigatório';
    if (!formData.destAddress.trim()) newErrors.destAddress = 'Endereço é obrigatório';
    if (!formData.destNumber.trim()) newErrors.destNumber = 'Número é obrigatório';
    if (!formData.destNeighborhood.trim()) newErrors.destNeighborhood = 'Bairro é obrigatório';
    if (!formData.destCity.trim()) newErrors.destCity = 'Cidade é obrigatória';
    if (!formData.destState.trim()) newErrors.destState = 'UF é obrigatório';
    if (!formData.destPhone.trim()) newErrors.destPhone = 'Telefone é obrigatório';

    // Required Package field
    if (!formData.weight.trim()) newErrors.weight = 'Peso é obrigatório';

    // Numeric validations
    if (formData.weight && isNaN(Number(formData.weight))) {
      newErrors.weight = 'Peso deve ser um número';
    }
    if (formData.height && isNaN(Number(formData.height))) {
      newErrors.height = 'Altura deve ser um número';
    }
    if (formData.width && isNaN(Number(formData.width))) {
      newErrors.width = 'Largura deve ser um número';
    }
    if (formData.length && isNaN(Number(formData.length))) {
      newErrors.length = 'Comprimento deve ser um número';
    }
    if (formData.declaredValue && isNaN(Number(formData.declaredValue))) {
      newErrors.declaredValue = 'Valor deve ser um número';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setIsLoading(true);

    // TODO: BLOCKED - Needs VIPP confirmation on:
    // 1. Remetente structure inside Volumes[]
    // 2. TipoAutorizacaoReversa values
    // 3. E-ticket field location in response
    console.log('Form data:', formData);
    console.log('Ticket:', ticket);

    // Placeholder - would call createReversa API here
    setTimeout(() => {
      setIsLoading(false);
      // onOpenChange(false);
    }, 1000);
  };

  const handleCancel = () => {
    onOpenChange(false);
  };

  // =============================================================================
  // Render Helpers
  // =============================================================================

  const renderInput = (
    field: keyof ReversaFormState,
    label: string,
    options?: {
      type?: string;
      placeholder?: string;
      icon?: React.ReactNode;
      required?: boolean;
      disabled?: boolean;
    }
  ) => {
    const { type = 'text', placeholder, icon, required = false, disabled = false } = options || {};
    const error = errors[field];

    return (
      <div className="space-y-1.5">
        <Label htmlFor={field} className="text-xs font-medium text-zinc-300">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </Label>
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400">
              {icon}
            </div>
          )}
          <Input
            id={field}
            type={type}
            value={formData[field]}
            onChange={(e) => handleInputChange(field, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            className={cn(
              'h-9 bg-zinc-900/50 border-zinc-700/50 text-zinc-100 placeholder:text-zinc-500',
              'focus:border-blue-500/50 focus:ring-blue-500/20',
              icon && 'pl-10',
              error && 'border-red-500/50 focus:border-red-500 focus:ring-red-500/20'
            )}
          />
        </div>
        {error && (
          <p className="text-xs text-red-400 flex items-center gap-1">
            <AlertCircle className="h-3 w-3" />
            {error}
          </p>
        )}
      </div>
    );
  };

  const renderSelect = (
    field: keyof ReversaFormState,
    label: string,
    options: Array<{ value: string; label: string }>,
    config?: { required?: boolean; icon?: React.ReactNode }
  ) => {
    const { required = false, icon } = config || {};

    return (
      <div className="space-y-1.5">
        <Label htmlFor={field} className="text-xs font-medium text-zinc-300">
          {label}
          {required && <span className="text-red-400 ml-1">*</span>}
        </Label>
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 z-10">
              {icon}
            </div>
          )}
          <select
            id={field}
            value={formData[field]}
            onChange={(e) => handleInputChange(field, e.target.value)}
            className={cn(
              'w-full h-9 bg-zinc-900/50 border border-zinc-700/50 text-zinc-100 rounded-md',
              'focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 outline-none',
              'text-sm px-3',
              icon && 'pl-10'
            )}
          >
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    );
  };

  // =============================================================================
  // Render
  // =============================================================================

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            {/* Backdrop */}
            <Dialog.Overlay asChild forceMount>
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
              />
            </Dialog.Overlay>

            {/* Content */}
            <Dialog.Content asChild forceMount>
              <motion.div
                initial={{ opacity: 0, scale: 0.95, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95, y: 20 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className={cn(
                  'fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50',
                  'w-full max-w-3xl max-h-[90vh] overflow-hidden',
                  'bg-gradient-to-br from-zinc-900/95 via-zinc-900/90 to-zinc-800/95',
                  'border border-zinc-700/50 rounded-2xl shadow-2xl',
                  'backdrop-blur-xl'
                )}
              >
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700/50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center">
                      <Package className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <Dialog.Title className="text-lg font-semibold text-zinc-100">
                        Gerar E-Ticket de Reversa
                      </Dialog.Title>
                      <p className="text-xs text-zinc-400 mt-0.5">
                        Preencha os dados para gerar o e-ticket de logística reversa
                      </p>
                    </div>
                  </div>
                  <Dialog.Close asChild>
                    <button
                      className={cn(
                        'w-8 h-8 rounded-lg flex items-center justify-center',
                        'hover:bg-zinc-800/50 transition-colors',
                        'text-zinc-400 hover:text-zinc-100'
                      )}
                      aria-label="Fechar"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </Dialog.Close>
                </div>

                {/* Body - Scrollable */}
                <div className="overflow-y-auto max-h-[calc(90vh-140px)] px-6 py-6">
                  <div className="space-y-8">
                    {/* Section: Remetente (Sender) - Matches VIPP Form */}
                    <section>
                      <h3 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center gap-2">
                        <User className="h-4 w-4 text-green-400" />
                        Informações do Remetente
                      </h3>
                      <div className="space-y-4">
                        {/* Row 1: CPF/CNPJ, Nome */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {renderInput('cpfCnpj', 'CPF/CNPJ', {
                            placeholder: '000.000.000-00',
                            required: true,
                          })}
                          <div className="md:col-span-2">
                            {renderInput('name', 'Nome', {
                              placeholder: 'Nome completo',
                              icon: <User className="h-4 w-4" />,
                              required: true,
                            })}
                          </div>
                        </div>

                        {/* Row 2: CEP, Endereço, Número */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          {renderInput('cep', 'CEP', {
                            placeholder: '00000-000',
                            required: true,
                          })}
                          <div className="md:col-span-2">
                            {renderInput('address', 'Endereço', {
                              placeholder: 'Rua, Avenida...',
                              required: true,
                            })}
                          </div>
                          {renderInput('number', 'Número', {
                            placeholder: '123',
                            required: true,
                          })}
                        </div>

                        {/* Row 3: Complemento, Bairro */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {renderInput('complement', 'Complemento', {
                            placeholder: 'Apto, Bloco...',
                          })}
                          {renderInput('neighborhood', 'Bairro', {
                            placeholder: 'Bairro',
                            required: true,
                          })}
                        </div>

                        {/* Row 4: Cidade, UF */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="md:col-span-2">
                            {renderInput('city', 'Cidade', {
                              placeholder: 'Cidade',
                              required: true,
                            })}
                          </div>
                          {renderInput('state', 'UF', {
                            placeholder: 'SP',
                            required: true,
                          })}
                        </div>

                        {/* Row 5: Telefone, Celular, Email */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {renderInput('phone', 'Telefone', {
                            placeholder: '(11) 3333-3333',
                            icon: <Phone className="h-4 w-4" />,
                            required: true,
                          })}
                          {renderInput('mobile', 'Celular', {
                            placeholder: '(11) 99999-9999',
                            icon: <Phone className="h-4 w-4" />,
                          })}
                          {renderInput('email', 'Email', {
                            type: 'email',
                            placeholder: 'email@exemplo.com',
                          })}
                        </div>
                      </div>
                    </section>

                    {/* Section: Destinatario (Recipient) */}
                    <section>
                      <h3 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-red-400" />
                        Informações do Destinatário
                      </h3>
                      <div className="space-y-4">
                        {/* Row 1: CPF/CNPJ, Nome */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {renderInput('destCpfCnpj', 'CPF/CNPJ', {
                            placeholder: '000.000.000-00',
                            required: true,
                          })}
                          <div className="md:col-span-2">
                            {renderInput('destName', 'Nome', {
                              placeholder: 'Nome completo',
                              icon: <User className="h-4 w-4" />,
                              required: true,
                            })}
                          </div>
                        </div>

                        {/* Row 2: CEP, Endereço, Número */}
                        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                          {renderInput('destCep', 'CEP', {
                            placeholder: '00000-000',
                            required: true,
                          })}
                          <div className="md:col-span-2">
                            {renderInput('destAddress', 'Endereço', {
                              placeholder: 'Rua, Avenida...',
                              required: true,
                            })}
                          </div>
                          {renderInput('destNumber', 'Número', {
                            placeholder: '123',
                            required: true,
                          })}
                        </div>

                        {/* Row 3: Complemento, Bairro */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {renderInput('destComplement', 'Complemento', {
                            placeholder: 'Apto, Bloco...',
                          })}
                          {renderInput('destNeighborhood', 'Bairro', {
                            placeholder: 'Bairro',
                            required: true,
                          })}
                        </div>

                        {/* Row 4: Cidade, UF */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          <div className="md:col-span-2">
                            {renderInput('destCity', 'Cidade', {
                              placeholder: 'Cidade',
                              required: true,
                            })}
                          </div>
                          {renderInput('destState', 'UF', {
                            placeholder: 'SP',
                            required: true,
                          })}
                        </div>

                        {/* Row 5: Telefone, Celular, Email */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {renderInput('destPhone', 'Telefone', {
                            placeholder: '(11) 3333-3333',
                            icon: <Phone className="h-4 w-4" />,
                            required: true,
                          })}
                          {renderInput('destMobile', 'Celular', {
                            placeholder: '(11) 99999-9999',
                            icon: <Phone className="h-4 w-4" />,
                          })}
                          {renderInput('destEmail', 'Email', {
                            type: 'email',
                            placeholder: 'email@exemplo.com',
                          })}
                        </div>
                      </div>
                    </section>

                    {/* Section: Package Information */}
                    <section>
                      <h3 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center gap-2">
                        <Package className="h-4 w-4 text-blue-400" />
                        Informações do Pacote
                      </h3>
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {renderInput('weight', 'Peso (kg)', {
                            type: 'number',
                            placeholder: '1.5',
                            icon: <Scale className="h-4 w-4" />,
                            required: true,
                          })}
                          {renderInput('declaredValue', 'Valor Declarado (R$)', {
                            type: 'number',
                            placeholder: '0.00',
                            icon: <DollarSign className="h-4 w-4" />,
                          })}
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                          {renderInput('height', 'Altura (cm)', {
                            type: 'number',
                            placeholder: '10',
                            icon: <Ruler className="h-4 w-4" />,
                          })}
                          {renderInput('width', 'Largura (cm)', {
                            type: 'number',
                            placeholder: '15',
                            icon: <Ruler className="h-4 w-4" />,
                          })}
                          {renderInput('length', 'Comprimento (cm)', {
                            type: 'number',
                            placeholder: '20',
                            icon: <Ruler className="h-4 w-4" />,
                          })}
                        </div>
                      </div>
                    </section>

                    {/* Section: Service Options */}
                    <section>
                      <h3 className="text-sm font-semibold text-zinc-100 mb-4 flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-400" />
                        Opções de Serviço
                      </h3>
                      <div className="space-y-4">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          {renderSelect(
                            'serviceType',
                            'Tipo de Serviço',
                            [
                              { value: 'PAC_REVERSA', label: 'PAC REVERSA (3301)' },
                              { value: 'SEDEX_REVERSA', label: 'SEDEX REVERSA (3247)' },
                            ],
                            { required: true }
                          )}
                          {renderSelect(
                            'costCenter',
                            'Centro de Custo',
                            COST_CENTERS.map((cc) => ({
                              value: cc.id,
                              label: cc.label,
                            })),
                            { required: true }
                          )}
                        </div>
                        <div>
                          <Label htmlFor="notes" className="text-xs font-medium text-zinc-300">
                            Observações
                          </Label>
                          <Textarea
                            id="notes"
                            value={formData.notes}
                            onChange={(e) => handleInputChange('notes', e.target.value)}
                            placeholder="Informações adicionais sobre a reversa..."
                            className={cn(
                              'mt-1.5 min-h-[80px] bg-zinc-900/50 border-zinc-700/50',
                              'text-zinc-100 placeholder:text-zinc-500',
                              'focus:border-blue-500/50 focus:ring-blue-500/20'
                            )}
                          />
                        </div>
                      </div>
                    </section>

                    {/* Info Banner */}
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="h-5 w-5 text-blue-400 mt-0.5 flex-shrink-0" />
                        <div className="space-y-1">
                          <p className="text-sm font-medium text-blue-100">
                            SCAFFOLD - Funcionalidade em desenvolvimento
                          </p>
                          <p className="text-xs text-blue-200/80">
                            O botão de geração está desabilitado enquanto aguardamos confirmação da VIPP sobre
                            a estrutura da API de reversa (Remetente, TipoAutorizacaoReversa, localização do e-ticket).
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-zinc-700/50 bg-zinc-900/50">
                  <Button
                    variant="outline"
                    onClick={handleCancel}
                    disabled={isLoading}
                    className={cn(
                      'h-9 px-4 bg-transparent border-zinc-700/50 text-zinc-300',
                      'hover:bg-zinc-800/50 hover:text-zinc-100 hover:border-zinc-600'
                    )}
                  >
                    Cancelar
                  </Button>
                  <Button
                    onClick={handleSubmit}
                    disabled={true} // TODO: Change to `disabled={isLoading}` when ready
                    className={cn(
                      'h-9 px-6 bg-gradient-to-r from-blue-500 to-blue-600',
                      'hover:from-blue-600 hover:to-blue-700',
                      'text-white font-medium shadow-lg shadow-blue-500/20',
                      'disabled:opacity-50 disabled:cursor-not-allowed'
                    )}
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Gerando...
                      </>
                    ) : (
                      'Gerar E-Ticket'
                    )}
                  </Button>
                </div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
