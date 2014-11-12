from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from .forms import ContactForm, DomainForm
from .whois import check_domain_availability
from .suggestion import suggest_domains


def domain(request):
    domain_form = DomainForm(request.GET)
    if request.method == "GET" and domain_form.is_valid():
        full_domain = domain_form.full_domain()
        available = check_domain_availability(full_domain)

        context = {
            "full_domain": full_domain,
            "available": available
        }

        if not available:
            initial_domain = (domain_form.cleaned_data["domain"],
                              domain_form.cleaned_data["tld"])
            context["suggested_domains"] = suggest_domains(initial_domain)
        return render(request, "domain.html", context)
    elif request.method == "POST":
        form = ContactForm(request.POST)
        address_list = request.POST.getlist("new_mail")

        if form.is_valid() and domain_form.is_valid():
            return redirect("{0}?domain={1}&tld={2}".format(
                reverse("contact"),
                domain_form.cleaned_data["domain"],
                domain_form.cleaned_data["tld"]))


def contact(request):
    domain_form = DomainForm(request.GET)
    if request.method == "GET":
        form = DomainForm(request.GET)
        if form.is_valid() and domain_form.is_valid():
            context = {
                "full_domain": domain_form.full_domain(),
                "available": check_domain_availability(domain_form.full_domain())
            }
            return render(request, "contact.html", context)
    elif request.method == "POST" and domain_form.is_valid():
        return redirect("{0}?domain={1}&tld={2}".format(
            reverse("payment"),
            domain_form.cleaned_data["domain"],
            domain_form.cleaned_data["tld"]))


def payment(request):
    domain_form = DomainForm(request.GET)
    if request.method == "GET" and domain_form.is_valid():
        context = {
            "full_domain": domain_form.full_domain(),
            "available": check_domain_availability(domain_form.full_domain())
        }

        return render(request, "payment.html", context)
